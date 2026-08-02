from __future__ import annotations

import unittest

from experiments.tau2_native_runner import (
    COMPATIBILITY_ID,
    compatibility_metadata,
    install_compatibility_shim,
)


class Tau2NativeRunnerTests(unittest.TestCase):
    def test_strict_dummy_user_is_shimmed_only_for_the_known_generic_kwargs(self) -> None:
        class StrictDummyUser:
            def __init__(self) -> None:
                self.initialized = True

        metadata = compatibility_metadata(StrictDummyUser)
        self.assertTrue(metadata["required"])
        installed = install_compatibility_shim(StrictDummyUser)
        self.assertTrue(installed["installed"])
        self.assertEqual(getattr(StrictDummyUser, "_local_action_dummy_user_compatibility"), COMPATIBILITY_ID)
        instance = StrictDummyUser(tools=[], instructions="ticket", llm="ignored", llm_args={}, persona_config=None)
        self.assertTrue(instance.initialized)
        with self.assertRaises(TypeError):
            StrictDummyUser(unexpected=True)

    def test_modern_dummy_user_is_not_patched(self) -> None:
        class ModernDummyUser:
            def __init__(self, *, tools=None, instructions=None, llm=None, llm_args=None, persona_config=None) -> None:
                self.values = (tools, instructions, llm, llm_args, persona_config)

        metadata = compatibility_metadata(ModernDummyUser)
        self.assertFalse(metadata["required"])
        installed = install_compatibility_shim(ModernDummyUser)
        self.assertFalse(installed["installed"])
        instance = ModernDummyUser(tools=["tool"], instructions="ticket", llm="local", llm_args={"temperature": 0}, persona_config=None)
        self.assertEqual(instance.values[0], ["tool"])
