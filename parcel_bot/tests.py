from django.test import SimpleTestCase


class ChatStreamTests(SimpleTestCase):
    async def test_chat_streams_sse_tokens(self):
        res = await self.async_client.post(
            "/chat/", {"message": "책 한 권 보내려고요"}, content_type="application/json"
        )
        self.assertEqual(res["Content-Type"], "text/event-stream")
        body = b"".join([chunk async for chunk in res.streaming_content]).decode()
        self.assertIn('data: {"token"', body)
        self.assertTrue(body.rstrip().endswith("data: [DONE]"))
