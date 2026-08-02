"""Dependency-free OpenAI-compatible local model adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping

from protocol.ir import require_valid_decision
from .base import ModelRequest


class LocalModelHTTPError(RuntimeError):
    pass


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Do not let a local model endpoint redirect a harness request elsewhere."""

    def redirect_request(self, request: urllib.request.Request, fp: Any, code: int, message: str, headers: Any, newurl: str) -> None:
        return None


class OpenAICompatibleAdapter:
    """Call a local `/v1/chat/completions` endpoint and enforce Action IR."""

    def __init__(self, base_url: str, model: str, *, api_key: str | None = None, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.requests: list[ModelRequest] = []
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    @staticmethod
    def parse_content(content: Any) -> Mapping[str, Any]:
        if not isinstance(content, str):
            raise LocalModelHTTPError("model response content must be text")
        text = content.strip()
        if text.startswith("```"):
            text = text.removeprefix("```").removeprefix("json").removesuffix("```").strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LocalModelHTTPError(f"model response was not JSON: {exc.msg}") from exc
        if not isinstance(value, Mapping):
            raise LocalModelHTTPError("model response JSON must be an object")
        return value

    def decide(self, request: ModelRequest) -> Mapping[str, Any]:
        self.requests.append(request)
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "Return exactly one JSON Action IR v0 decision. Do not include markdown."},
                {"role": "user", "content": request.context},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request_url = self.base_url + "/v1/chat/completions" if not self.base_url.endswith("/v1") else self.base_url + "/chat/completions"
        http_request = urllib.request.Request(request_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        # Keep the provider socket timeout inside the harness-owned decision
        # budget.  The adapter-level timeout remains a deployment ceiling,
        # while the request budget is the authoritative per-step limit.
        budget_seconds = request.budget.get("seconds")
        request_timeout = self.timeout_seconds
        if isinstance(budget_seconds, (int, float)) and budget_seconds > 0:
            request_timeout = min(request_timeout, float(budget_seconds))
        request_timeout = max(0.1, request_timeout)
        try:
            with self._opener.open(http_request, timeout=request_timeout) as response:
                document = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LocalModelHTTPError(f"local model request failed: {exc}") from exc
        try:
            content = document["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalModelHTTPError("local model response lacked choices[0].message.content") from exc
        return require_valid_decision(self.parse_content(content))
