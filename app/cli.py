"""CLI and localhost API for the launch candidate."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import ssl
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from adapters.http import OpenAICompatibleAdapter
from app.service import run_action
from app.storage import TraceStore
from app.mcp import serve_stdio
from traces.replay import load_file, load_jsonl
from tools.memory_workspace import make_memory_registry


def _json_response(handler: BaseHTTPRequestHandler, status: int, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("X-Harness-API-Version", "1")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _unauthorized(handler: BaseHTTPRequestHandler) -> None:
    payload = json.dumps({"schema": "open-agent-harness-api-error/v1", "error": "authentication required"}).encode("utf-8")
    handler.send_response(401)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("WWW-Authenticate", "Bearer")
    handler.send_header("X-Harness-API-Version", "1")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _rate_limited(handler: BaseHTTPRequestHandler, retry_after: int) -> None:
    payload = json.dumps({"schema": "open-agent-harness-api-error/v1", "error": "rate limit exceeded"}).encode("utf-8")
    handler.send_response(429)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Retry-After", str(max(1, retry_after)))
    handler.send_header("X-Harness-API-Version", "1")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP listener with a bounded pre-auth connection surface."""

    daemon_threads = True

    def __init__(
        self,
        *args: Any,
        connection_timeout_seconds: float = 10.0,
        max_connections: int = 64,
        **kwargs: Any,
    ) -> None:
        if not 0.1 <= connection_timeout_seconds <= 300.0:
            raise ValueError("connection_timeout_seconds must be between 0.1 and 300 seconds")
        if not 1 <= max_connections <= 4_096:
            raise ValueError("max_connections must be between 1 and 4,096")
        super().__init__(*args, **kwargs)
        self.connection_timeout_seconds = float(connection_timeout_seconds)
        self.max_connections = max_connections
        self._connection_slots = threading.BoundedSemaphore(max_connections)

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._connection_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            request.settimeout(self.connection_timeout_seconds)
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()


def _server(
    trace_dir: str | None = None,
    auth_token: str | None = None,
    auth_tokens: Mapping[str, str] | None = None,
    rate_limit_per_minute: int = 120,
    model_endpoint: str | None = None,
    model: str | None = None,
) -> type[BaseHTTPRequestHandler]:
    if auth_token is not None and auth_tokens is not None:
        raise ValueError("auth_token and auth_tokens are mutually exclusive")
    if not 1 <= rate_limit_per_minute <= 100_000:
        raise ValueError("rate_limit_per_minute must be between 1 and 100,000")
    request_times: dict[str, deque[float]] = {}
    request_times_lock = threading.Lock()
    configured_adapter, configured_model_name = (
        _optional_local_adapter({"model_endpoint": model_endpoint, "model": model})
        if model_endpoint is not None or model is not None
        else (None, "local-service-policy")
    )

    def trace_root(principal: str) -> str | None:
        if trace_dir is None:
            return None
        if auth_tokens is None:
            return trace_dir
        # Never use a user-controlled principal as a filesystem component.
        suffix = hashlib.sha256(principal.encode("utf-8")).hexdigest()[:32]
        return str(Path(trace_dir) / f"tenant-{suffix}")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _principal(self) -> str | None:
            if auth_token is None and auth_tokens is None:
                return "local"
            supplied = self.headers.get("Authorization", "")
            if auth_token is not None:
                expected = f"Bearer {auth_token}"
                if hmac.compare_digest(supplied, expected):
                    return "default"
            if auth_tokens is not None:
                for principal, token in auth_tokens.items():
                    if hmac.compare_digest(supplied, f"Bearer {token}"):
                        return principal
            _unauthorized(self)
            return None

        def _admitted(self, principal: str) -> bool:
            now = time.monotonic()
            cutoff = now - 60.0
            with request_times_lock:
                timestamps = request_times.setdefault(principal, deque())
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if len(timestamps) >= rate_limit_per_minute:
                    retry_after = max(1, int(60.0 - (now - timestamps[0])))
                    _rate_limited(self, retry_after)
                    return False
                timestamps.append(now)
            return True

        def do_GET(self) -> None:  # noqa: N802
            principal = self._principal()
            if principal is None:
                return
            if not self._admitted(principal):
                return
            if self.path == "/health":
                _json_response(self, 200, {"schema": "open-agent-harness-api/v1", "status": "ok", "service": "open-agent-harness-os", "version": "0.1", "trace_retention": trace_dir is not None, "tenant_isolation": auth_tokens is not None})
                return
            if self.path == "/tools":
                _, registry = make_memory_registry()
                _json_response(self, 200, {"schema": "open-agent-harness-api/v1", "tools": [registry.metadata(name) for name in registry.names()]})
                return
            if self.path == "/traces":
                root = trace_root(principal)
                store = TraceStore(root) if root is not None else None
                _json_response(self, 200, {"schema": "open-agent-harness-api/v1", "traces": store.list() if store else []})
                return
            if self.path.startswith("/traces/") and trace_root(principal) is not None:
                digest = self.path.removeprefix("/traces/")
                try:
                    value = TraceStore(trace_root(principal)).read(digest)
                except (FileNotFoundError, ValueError):
                    _json_response(self, 404, {"schema": "open-agent-harness-api-error/v1", "error": "trace not found"})
                    return
                _json_response(self, 200, {"schema": "open-agent-harness-api/v1", "digest": digest, "trace_jsonl": value})
                return
            _json_response(self, 404, {"schema": "open-agent-harness-api-error/v1", "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            principal = self._principal()
            if principal is None:
                return
            if not self._admitted(principal):
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("request body must be between 1 byte and 1 MB")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                if self.path == "/run":
                    required = {"task_id", "prompt", "tool", "arguments"}
                    if not isinstance(body, dict) or not required.issubset(body):
                        raise ValueError("/run requires task_id, prompt, tool, and arguments")
                    if "model_endpoint" in body or "model" in body:
                        raise ValueError("/run model_endpoint and model are configured by the server operator")
                    result = run_action(body["task_id"], body["prompt"], body["tool"], body["arguments"], variant=body.get("variant", "H1"), adapter=configured_adapter, model_name=configured_model_name, initial_files=body.get("initial_files"), max_steps=int(body.get("max_steps", 4)), timeout_seconds=float(body.get("timeout_seconds", 5.0)), token_budget=int(body.get("token_budget", 1800)), trace_dir=trace_root(principal))
                    _json_response(self, 200, result)
                    return
                if self.path == "/replay":
                    trace = load_jsonl(str(body.get("trace_jsonl", "")).splitlines())
                    _json_response(self, 200, {"schema": "open-agent-harness-api/v1", "events": len(trace.events), "valid": trace.validate(require_end=True) == []})
                    return
                _json_response(self, 404, {"schema": "open-agent-harness-api-error/v1", "error": "not found"})
            except Exception as exc:
                _json_response(self, 400, {"schema": "open-agent-harness-api-error/v1", "error": f"{type(exc).__name__}: {exc}"})

    return Handler


def _optional_local_adapter(value: dict[str, Any]) -> tuple[Any, str]:
    endpoint = value.get("model_endpoint")
    model = value.get("model")
    if endpoint is None and model is None:
        return None, "local-service-policy"
    if not isinstance(endpoint, str) or not isinstance(model, str) or not endpoint or not model:
        raise ValueError("model_endpoint and model must be provided together")
    parsed = urlparse(endpoint)
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("model_endpoint must use a valid port") from exc
    path = parsed.path.rstrip("/")
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.params
        or parsed.query
        or parsed.fragment
        or path not in {"", "/v1"}
    ):
        raise ValueError("model_endpoint must be a canonical localhost HTTP(S) root or /v1 URL")
    canonical_endpoint = f"{parsed.scheme}://{parsed.netloc}{'/v1' if path == '/v1' else ''}"
    return OpenAICompatibleAdapter(canonical_endpoint, model), model


def _validate_bind_host(host: str, allow_non_loopback: bool = False) -> None:
    if not allow_non_loopback and host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("server host must be loopback unless --allow-non-loopback is explicit")


def _validate_server_security(
    host: str,
    *,
    allow_non_loopback: bool,
    auth_token: str | None,
    auth_tokens: Mapping[str, str] | None = None,
    tls_certfile: str | None,
    tls_keyfile: str | None,
    connection_timeout_seconds: float = 10.0,
    max_connections: int = 64,
) -> None:
    """Validate the deployment boundary before opening a listening socket."""
    _validate_bind_host(host, allow_non_loopback)
    if auth_token is not None and len(auth_token) < 16:
        raise ValueError("--auth-token/HARNESS_AUTH_TOKEN must contain at least 16 characters")
    if auth_token is not None and auth_tokens is not None:
        raise ValueError("--auth-token and --auth-token-file are mutually exclusive")
    if auth_tokens is not None:
        if not auth_tokens:
            raise ValueError("--auth-token-file must contain at least one principal")
        if any(not isinstance(principal, str) or not principal or not isinstance(token, str) or len(token) < 16 for principal, token in auth_tokens.items()):
            raise ValueError("every auth-token-file principal must map to a token of at least 16 characters")
    if (tls_certfile is None) != (tls_keyfile is None):
        raise ValueError("--tls-certfile and --tls-keyfile must be provided together")
    if allow_non_loopback and not (auth_token or auth_tokens):
        raise ValueError("--allow-non-loopback requires --auth-token or HARNESS_AUTH_TOKEN")
    if allow_non_loopback and not (tls_certfile and tls_keyfile):
        raise ValueError("--allow-non-loopback requires --tls-certfile and --tls-keyfile")
    if not 0.1 <= connection_timeout_seconds <= 300.0:
        raise ValueError("--connection-timeout-seconds must be between 0.1 and 300")
    if not 1 <= max_connections <= 4_096:
        raise ValueError("--max-connections must be between 1 and 4,096")


def _load_auth_tokens(path: str | Path) -> dict[str, str]:
    """Load and shape a principal-to-token JSON object before validation."""
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read --auth-token-file: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("--auth-token-file must contain a JSON object mapping principals to tokens")
    return {str(principal): token for principal, token in loaded.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("tools")
    demo = sub.add_parser("demo")
    demo.add_argument("--trace-out")
    run = sub.add_parser("run")
    run.add_argument("--task-id", required=True)
    run.add_argument("--prompt", required=True)
    run.add_argument("--tool", required=True)
    run.add_argument("--arguments-json", default="{}")
    run.add_argument("--argument", action="append", default=[], help="repeat as key=value; avoids shell JSON quoting")
    run.add_argument("--model-endpoint")
    run.add_argument("--model")
    run.add_argument("--initial-file", action="append", default=[], help="repeat as path=content")
    run.add_argument("--max-steps", type=int, default=4)
    run.add_argument("--timeout-seconds", type=float, default=5.0)
    run.add_argument("--token-budget", type=int, default=1800)
    run.add_argument("--trace-dir")
    run.add_argument("--variant", choices=("H0", "H1", "H2", "H3", "H4"), default="H1")
    replay = sub.add_parser("replay")
    replay.add_argument("trace")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--trace-dir")
    serve.add_argument("--allow-non-loopback", action="store_true", help="allow non-loopback serving; requires --auth-token or HARNESS_AUTH_TOKEN")
    serve.add_argument("--auth-token", help="Bearer token required for every HTTP request; may also be set with HARNESS_AUTH_TOKEN")
    serve.add_argument("--auth-token-file", help="JSON object mapping principal names to bearer tokens for isolated trace tenants")
    serve.add_argument("--rate-limit-per-minute", type=int, default=120, help="maximum authenticated requests per principal per rolling minute")
    serve.add_argument("--model-endpoint", help="operator-owned loopback OpenAI-compatible endpoint; HTTP callers cannot override it")
    serve.add_argument("--model", help="model identifier paired with --model-endpoint")
    serve.add_argument("--connection-timeout-seconds", type=float, default=10.0, help="per-connection header/body/TLS-read deadline")
    serve.add_argument("--max-connections", type=int, default=64, help="maximum concurrent HTTP connections before excess sockets are closed")
    serve.add_argument("--tls-certfile", help="PEM certificate chain for HTTPS serving")
    serve.add_argument("--tls-keyfile", help="PEM private key for HTTPS serving")
    sub.add_parser("mcp", help="serve the verification kernel over MCP stdio")
    args = parser.parse_args()

    if args.command == "tools":
        _, registry = make_memory_registry()
        print(json.dumps({"tools": [registry.metadata(name) for name in registry.names()]}, indent=2, sort_keys=True))
        return 0
    if args.command == "demo":
        result = run_action("product-demo", "Write demo.txt with hello.", "write_file", {"path": "demo.txt", "content": "hello"})
        if args.trace_out:
            Path(args.trace_out).write_text(result["trace_jsonl"], encoding="utf-8")
        print(json.dumps({key: value for key, value in result.items() if key != "trace_jsonl"}, indent=2, sort_keys=True))
        return 0
    if args.command == "run":
        arguments = json.loads(args.arguments_json)
        for item in args.argument:
            if "=" not in item:
                parser.error("--argument must use key=value")
            key, value = item.split("=", 1)
            arguments[key] = value
        initial_files = {}
        for item in args.initial_file:
            if "=" not in item:
                parser.error("--initial-file must use path=content")
            key, value = item.split("=", 1)
            initial_files[key] = value
        adapter, model_name = _optional_local_adapter({"model_endpoint": args.model_endpoint, "model": args.model}) if (args.model_endpoint or args.model) else (None, "local-service-policy")
        result = run_action(args.task_id, args.prompt, args.tool, arguments, variant=args.variant, adapter=adapter, model_name=model_name, initial_files=initial_files, max_steps=args.max_steps, timeout_seconds=args.timeout_seconds, token_budget=args.token_budget, trace_dir=args.trace_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "replay":
        trace = load_file(args.trace)
        print(json.dumps({"events": len(trace.events), "valid": trace.validate(require_end=True) == [], "issues": trace.validate(require_end=True)}, indent=2))
        return 0
    if args.command == "mcp":
        return serve_stdio()
    auth_token = args.auth_token if args.auth_token is not None else os.environ.get("HARNESS_AUTH_TOKEN")
    auth_tokens: dict[str, str] | None = None
    if args.auth_token_file:
        if args.auth_token is not None or os.environ.get("HARNESS_AUTH_TOKEN") is not None:
            parser.error("--auth-token-file cannot be combined with --auth-token or HARNESS_AUTH_TOKEN")
        try:
            auth_tokens = _load_auth_tokens(args.auth_token_file)
        except ValueError as exc:
            parser.error(str(exc))
        auth_token = None
    try:
        _validate_server_security(
            args.host,
            allow_non_loopback=args.allow_non_loopback,
            auth_token=auth_token,
            auth_tokens=auth_tokens,
            tls_certfile=args.tls_certfile,
            tls_keyfile=args.tls_keyfile,
            connection_timeout_seconds=args.connection_timeout_seconds,
            max_connections=args.max_connections,
        )
    except ValueError as exc:
        parser.error(str(exc))
    try:
        handler = _server(
            args.trace_dir,
            auth_token,
            auth_tokens,
            args.rate_limit_per_minute,
            args.model_endpoint,
            args.model,
        )
    except ValueError as exc:
        parser.error(str(exc))
    server = BoundedThreadingHTTPServer(
        (args.host, args.port),
        handler,
        connection_timeout_seconds=args.connection_timeout_seconds,
        max_connections=args.max_connections,
    )
    scheme = "http"
    if args.tls_certfile and args.tls_keyfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=args.tls_certfile, keyfile=args.tls_keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
        scheme = "https"
    print(json.dumps({"listening": f"{scheme}://{args.host}:{args.port}", "tls": scheme == "https", "tenant_isolation": auth_tokens is not None, "connection_timeout_seconds": args.connection_timeout_seconds, "max_connections": args.max_connections, "endpoints": ["/health", "/tools", "/run", "/replay", "/traces"]}))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
