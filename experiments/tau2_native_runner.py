"""Transparent compatibility entrypoint for τ³-bench's official text runner.

τ³-bench v1.0.1 registers ``DummyUser`` for its documented solo condition,
but its CLI constructs that class with five generic user arguments while the
class's constructor accepts none.  This wrapper applies a narrowly scoped,
in-memory constructor compatibility shim only when the installed source needs
it, then delegates directly to ``tau2.cli.main``.  It never edits the pinned
τ³-bench checkout, task set, environment, grader, or simulation logic.
"""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any


COMPATIBILITY_ID = "tau2-dummy-user-constructor-v1"
REQUIRED_DUMMY_USER_KWARGS = frozenset({"tools", "instructions", "llm", "llm_args", "persona_config"})


def _accepts_keyword(signature: inspect.Signature, name: str) -> bool:
    parameter = signature.parameters.get(name)
    if parameter is not None and parameter.kind in {
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }:
        return True
    return any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values())


def compatibility_metadata(dummy_user_type: type[Any]) -> dict[str, Any]:
    """Describe whether the official DummyUser constructor needs the shim."""

    signature = inspect.signature(dummy_user_type.__init__)
    accepted = sorted(name for name in REQUIRED_DUMMY_USER_KWARGS if _accepts_keyword(signature, name))
    missing = sorted(REQUIRED_DUMMY_USER_KWARGS - set(accepted))
    return {
        "id": COMPATIBILITY_ID,
        "constructor_signature": str(signature),
        "required_kwargs": sorted(REQUIRED_DUMMY_USER_KWARGS),
        "accepted_kwargs": accepted,
        "missing_kwargs": missing,
        "required": bool(missing),
        "scope": "in-memory DummyUser constructor compatibility only; no τ³-bench source, task, environment, grader, or simulation modification",
    }


def install_compatibility_shim(dummy_user_type: type[Any]) -> dict[str, Any]:
    """Install the minimal constructor shim if the imported class requires it."""

    metadata = compatibility_metadata(dummy_user_type)
    if not metadata["required"]:
        return {**metadata, "installed": False}
    if getattr(dummy_user_type, "_local_action_dummy_user_compatibility", None) == COMPATIBILITY_ID:
        return {**metadata, "installed": True, "already_installed": True}

    original_init = dummy_user_type.__init__

    @wraps(original_init)
    def compatible_init(self: Any, *args: Any, **kwargs: Any) -> None:
        if args or not set(kwargs).issubset(REQUIRED_DUMMY_USER_KWARGS):
            original_init(self, *args, **kwargs)
            return
        original_init(self)

    dummy_user_type.__init__ = compatible_init
    setattr(dummy_user_type, "_local_action_dummy_user_compatibility", COMPATIBILITY_ID)
    return {**metadata, "installed": True, "already_installed": False}


def main() -> int:
    from tau2.user.user_simulator import DummyUser

    install_compatibility_shim(DummyUser)
    from tau2.cli import main as tau2_main

    tau2_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
