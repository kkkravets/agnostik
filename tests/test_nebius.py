import asyncio
from types import MethodType
import unittest

from agnostik.nebius import NebiusProvider


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
