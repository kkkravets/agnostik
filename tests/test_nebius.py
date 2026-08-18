import unittest

from agnostik.nebius import DEFAULT_NEBIUS_BASE_URL, NebiusProvider


class NebiusProviderTests(unittest.TestCase):
    def test_uses_token_factory_by_default(self) -> None:
        provider = NebiusProvider(model="test/model", api_key="test-key")

        self.assertEqual(provider._base_url, DEFAULT_NEBIUS_BASE_URL)

    def test_forces_the_single_tool_by_name(self) -> None:
        provider = NebiusProvider(model="test/model", api_key="test-key")
        tool = {
            "type": "function",
            "function": {"name": "extract", "parameters": {"type": "object"}},
        }

        kwargs = provider._build_create_kwargs([], [tool], temperature=0)

        self.assertEqual(
            kwargs["tool_choice"],
            {"type": "function", "function": {"name": "extract"}},
        )
        self.assertEqual(kwargs["model"], "test/model")
        self.assertEqual(kwargs["tools"], [tool])
        self.assertEqual(kwargs["temperature"], 0)

    def test_rejects_ambiguous_tool_lists(self) -> None:
        provider = NebiusProvider(model="test/model", api_key="test-key")

        with self.assertRaisesRegex(ValueError, "exactly one"):
            provider._build_create_kwargs([], [])


if __name__ == "__main__":
    unittest.main()
