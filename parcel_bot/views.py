import asyncio
import json

from asgiref.sync import sync_to_async
from django.http import HttpRequest, StreamingHttpResponse

from parcel_bot.graph import chat_graph

_STREAM_END = object()


def _sse(token: str) -> str:
    return f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"


def _message(request: HttpRequest) -> str:
    return json.loads(request.body or "{}").get("message", "")


async def _mock_llm(message: str):
    # 고정 답변을 토큰 단위로 흘리는 가짜 LLM. 균일한 300ms 간격이 스트리밍 관측의 기준선이 된다.
    # 실제 LLM 연동은 metadata 추출이 필요해지는 버전에서 옵션으로 추가 예정.
    reply = (
        f"'{message}' 문의 확인했습니다. 배송 접수를 도와드릴게요. "
        "보내시는 분 성함과 받으시는 분 주소를 알려주세요."
    )
    for token in reply.split(" "):
        await asyncio.sleep(0.3)
        yield token + " "


async def chat(request: HttpRequest) -> StreamingHttpResponse:
    message = _message(request)

    async def stream():
        async for token in _mock_llm(message):
            yield _sse(token)
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(stream(), content_type="text/event-stream")


def graph_sync(request: HttpRequest) -> StreamingHttpResponse:
    # 동기 view + graph.stream() (동기 generator) — WSGI 와 매칭, ASGI 에서는 통째 버퍼링
    message = _message(request)

    def stream():
        for token in chat_graph.stream({"message": message}, stream_mode="custom"):
            yield _sse(token)
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(stream(), content_type="text/event-stream")


async def graph_async(request: HttpRequest) -> StreamingHttpResponse:
    # async view + graph.astream() (async generator) — ASGI 와 매칭, WSGI 에서는 통째 버퍼링
    message = _message(request)

    async def stream():
        async for token in chat_graph.astream({"message": message}, stream_mode="custom"):
            yield _sse(token)
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(stream(), content_type="text/event-stream")


async def graph_bridge(request: HttpRequest) -> StreamingHttpResponse:
    # 동기 graph.stream() 을 async generator 로 감싸 한 개씩 꺼내는 브리지 — ASGI 에서도 실스트리밍
    message = _message(request)

    async def stream():
        events = chat_graph.stream({"message": message}, stream_mode="custom")
        while True:
            token = await sync_to_async(next, thread_sensitive=True)(events, _STREAM_END)
            if token is _STREAM_END:
                break
            yield _sse(token)
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(stream(), content_type="text/event-stream")
