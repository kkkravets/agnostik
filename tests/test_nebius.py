import asyncio
from types import MethodType
import unittest

from types import SimpleNamespace

from agnostik.nebius import EmptyToolCallError, NebiusProvider


class FakeAsyncClient:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class NebiusProviderTests(unittest.TestCase):
    def test_complete_reuses_event_loop_and_close_releases_client(self):
        provider = NebiusProvider(model="test-model", api_key="test-key")
        client = FakeAsyncClient()
        provider._async_client = client
        loop_ids = []

        async def fake_complete(self, messages, tools, **kwargs):
            loop_ids.append(id(asyncio.get_running_loop()))
            return {"ok": True}

        provider.async_complete = MethodType(fake_complete, provider)

        self.assertEqual(provider.complete([], []), {"ok": True})
        self.assertEqual(provider.complete([], []), {"ok": True})
        provider.close()

        self.assertEqual(len(set(loop_ids)), 1)
        self.assertTrue(client.closed)


def chunk(*, arguments=None, content=None, reasoning=None, finish=None):
    tool_calls = [SimpleNamespace(function=SimpleNamespace(arguments=arguments))] if arguments is not None else None
    delta = SimpleNamespace(tool_calls=tool_calls, content=content, reasoning=reasoning)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)])


class FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        async def generate():
            for item in self._chunks:
                yield item

        return generate()

    async def close(self):
        pass


def provider_replying_with(*chunks):
    provider = NebiusProvider(model="test-model", api_key="test-key")

    async def create(**kwargs):
        return FakeStream(list(chunks))

    provider._async_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    tool = {"type": "function", "function": {"name": "f", "parameters": {"type": "object"}}}
    return lambda: asyncio.run(provider.async_complete([{"role": "user", "content": "hi"}], [tool]))


class OutputLimitTests(unittest.TestCase):
    tool = {"type": "function", "function": {"name": "f", "parameters": {"type": "object"}}}

    def test_output_limit_is_sent_only_when_set(self):
        limited = NebiusProvider(model="m", api_key="k", max_output_tokens=32000)
        self.assertEqual(limited._build_create_kwargs([], [self.tool])["max_tokens"], 32000)
        default = NebiusProvider(model="m", api_key="k")
        self.assertNotIn("max_tokens", default._build_create_kwargs([], [self.tool]))


class EmptyToolCallTests(unittest.TestCase):
    def test_a_complete_tool_call_is_parsed(self):
        call = provider_replying_with(chunk(arguments='{"a": '), chunk(arguments="1}", finish="tool_calls"))
        self.assertEqual(call(), {"a": 1})

    def test_empty_stream_names_the_likely_causes(self):
        with self.assertRaisesRegex(EmptyToolCallError, r"empty stream.*too large") as caught:
            provider_replying_with()()
        self.assertIn("finish_reason=none", str(caught.exception))
        self.assertIn("test-model", str(caught.exception))

    def test_output_limit_reached_while_reasoning_is_reported(self):
        call = provider_replying_with(chunk(reasoning="thinking " * 50), chunk(finish="length"))
        with self.assertRaisesRegex(EmptyToolCallError, r"finish_reason=length.*output-token limit.*reasoning"):
            call()

    def test_plain_text_answer_instead_of_a_tool_call_is_reported(self):
        call = provider_replying_with(chunk(content="I cannot do that."), chunk(finish="stop"))
        with self.assertRaisesRegex(EmptyToolCallError, r"I cannot do that.*plain-text answer"):
            call()

    def test_truncated_arguments_are_reported(self):
        call = provider_replying_with(chunk(arguments='{"a": '), chunk(finish="stop"))
        with self.assertRaisesRegex(EmptyToolCallError, "cut off or malformed"):
            call()
