from unittest import mock

from django.test import SimpleTestCase

from parcel_bot import views


def _assert_sse_body(testcase: SimpleTestCase, res, body: str) -> None:
    testcase.assertEqual(res["Content-Type"], "text/event-stream")
    testcase.assertIn('data: {"token"', body)
    testcase.assertTrue(body.rstrip().endswith("data: [DONE]"))


class ChatStreamTests(SimpleTestCase):
    async def test_chat_streams_sse_tokens(self):
        res = await self.async_client.post(
            "/chat/", {"message": "책 한 권 보내려고요"}, content_type="application/json"
        )
        body = b"".join([chunk async for chunk in res.streaming_content]).decode()
        _assert_sse_body(self, res, body)


class ChatPageTests(SimpleTestCase):
    def test_index_serves_chat_page(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"parcel-bot", res.content)


class UpstreamErrorTests(SimpleTestCase):
    async def test_upstream_error_emits_error_event(self):
        res = await self.async_client.post(
            "/chat/", {"message": "오류 재현"}, content_type="application/json"
        )
        body = b"".join([chunk async for chunk in res.streaming_content]).decode()
        self.assertIn("event: error", body)
        self.assertIn("upstream LLM", body)
        self.assertNotIn("[DONE]", body)


class KeepaliveTests(SimpleTestCase):
    async def test_slow_first_token_emits_keepalive(self):
        with (
            mock.patch.object(views, "SLOW_FIRST_TOKEN_S", 0.5),
            mock.patch.object(views, "KEEPALIVE_INTERVAL_S", 0.1),
        ):
            res = await self.async_client.post(
                "/chat/", {"message": "느림 재현"}, content_type="application/json"
            )
            body = b"".join([chunk async for chunk in res.streaming_content]).decode()
        self.assertIn(": keepalive", body)
        self.assertIn("[DONE]", body)


class GraphStreamTests(SimpleTestCase):
    def test_graph_sync_streams_sse_tokens(self):
        res = self.client.post(
            "/graph/sync/", {"message": "책 보내려고요"}, content_type="application/json"
        )
        body = b"".join(res.streaming_content).decode()
        _assert_sse_body(self, res, body)

    async def test_graph_async_streams_sse_tokens(self):
        res = await self.async_client.post(
            "/graph/async/", {"message": "책 보내려고요"}, content_type="application/json"
        )
        body = b"".join([chunk async for chunk in res.streaming_content]).decode()
        _assert_sse_body(self, res, body)

    async def test_graph_bridge_streams_sse_tokens(self):
        res = await self.async_client.post(
            "/graph/bridge/", {"message": "책 보내려고요"}, content_type="application/json"
        )
        body = b"".join([chunk async for chunk in res.streaming_content]).decode()
        _assert_sse_body(self, res, body)
