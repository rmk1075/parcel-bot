import asyncio
import json
from pathlib import Path

from asgiref.sync import sync_to_async
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse

from parcel_bot.graph import chat_graph

_STREAM_END = object()


def _sse(token: str) -> str:
    return f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"


def _message(request: HttpRequest) -> str:
    return json.loads(request.body or "{}").get("message", "")


def index(request: HttpRequest) -> HttpResponse:
    html = (Path(__file__).parent / "chat.html").read_text()
    return HttpResponse(html, content_type="text/html; charset=utf-8")


async def _mock_llm(message: str):
    # 고정 답변을 토큰 단위로 흘리는 가짜 LLM. 균일한 300ms 간격이 스트리밍 관측의 기준선이 된다.
    # 메시지에 "오류" 가 들어 있으면 네 번째 토큰에서 실패해 upstream 중단을 재현한다.
    reply = (
        f"'{message}' 문의 확인했습니다. 배송 접수를 도와드릴게요. "
        "보내시는 분 성함과 받으시는 분 주소를 알려주세요."
    )
    for i, token in enumerate(reply.split(" ")):
        await asyncio.sleep(0.3)
        if "오류" in message and i == 3:
            raise RuntimeError("upstream LLM 스트림이 중단되었습니다")
        yield token + " "


async def chat(request: HttpRequest) -> StreamingHttpResponse:
    message = _message(request)

    async def stream():
        try:
            async for token in _mock_llm(message):
                yield _sse(token)
            yield "data: [DONE]\n\n"
        except RuntimeError as e:
            # 케이스 4 (업스트림 중단): 클라이언트 연결은 살아 있으므로 에러를 SSE 이벤트로 알린다.
            payload = json.dumps({"message": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {payload}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            # 케이스 1 (클라이언트 이탈): 실서비스라면 여기서 LLM 스트림을 취소해 비용을 아낀다.
            print(f"client disconnected, cancelling stream: message={message!r}", flush=True)
            raise

    return StreamingHttpResponse(stream(), content_type="text/event-stream")


def graph_sync(request: HttpRequest) -> StreamingHttpResponse:
    # sync view + graph.stream() (sync generator). WSGI 와 매칭, ASGI 에서는 통째 버퍼링
    message = _message(request)

    def stream():
        for token in chat_graph.stream({"message": message}, stream_mode="custom"):
            yield _sse(token)
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(stream(), content_type="text/event-stream")


async def graph_async(request: HttpRequest) -> StreamingHttpResponse:
    # async view + graph.astream() (async generator). ASGI 와 매칭, WSGI 에서는 통째 버퍼링
    message = _message(request)

    async def stream():
        async for token in chat_graph.astream({"message": message}, stream_mode="custom"):
            yield _sse(token)
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(stream(), content_type="text/event-stream")


async def graph_bridge(request: HttpRequest) -> StreamingHttpResponse:
    # sync graph.stream() 을 async generator 로 감싸 한 개씩 꺼내는 브리지. ASGI 에서도 실스트리밍
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
