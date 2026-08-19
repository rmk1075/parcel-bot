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


# 무토큰 구간이 이 간격을 넘으면 연결이 살아 있다는 신호(SSE comment)를 보낸다.
KEEPALIVE_INTERVAL_S = 1.0
# "느림" 트리거 시 첫 토큰 전 침묵 시간. LLM 의 thinking·tool 호출 구간을 재현한다.
SLOW_FIRST_TOKEN_S = 10.0


async def _mock_llm(message: str):
    # 고정 답변을 토큰 단위로 흘리는 가짜 LLM. 균일한 300ms 간격이 스트리밍 관측의 기준선이 된다.
    # 메시지에 "오류" 가 들어 있으면 네 번째 토큰에서 실패해 upstream 중단을 재현한다.
    # 메시지에 "느림" 이 들어 있으면 첫 토큰 전에 침묵해 늦은 첫 토큰(TTFT)을 재현한다.
    if "느림" in message:
        await asyncio.sleep(SLOW_FIRST_TOKEN_S)
    reply = (
        f"'{message}' 문의 확인했습니다. 배송 접수를 도와드릴게요. "
        "보내시는 분 성함과 받으시는 분 주소를 알려주세요."
    )
    for i, token in enumerate(reply.split(" ")):
        await asyncio.sleep(0.3)
        if "오류" in message and i == 3:
            raise RuntimeError("upstream LLM 스트림이 중단되었습니다")
        yield token + " "


# 완주 정책: 생성 task 가 끝날 때까지 GC 되지 않도록 강한 참조를 유지한다.
_generation_tasks: set = set()


async def _generate(message: str, queue: asyncio.Queue) -> None:
    # 생성은 연결과 분리된 task 로 돈다. 연결이 끊겨도 여기는 끝까지 실행된다.
    text = ""
    try:
        async for token in _mock_llm(message):
            text += token
            await queue.put(("token", token))
        await queue.put(("done", None))
        # 실서비스라면 이 시점에 완성본을 대화 이력에 저장한다.
        print(f"generation finished: message={message!r} reply={text!r}", flush=True)
    except RuntimeError as e:
        await queue.put(("error", str(e)))
        print(f"generation failed: message={message!r} error={e}", flush=True)


async def chat(request: HttpRequest) -> StreamingHttpResponse:
    message = _message(request)
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_generate(message, queue))
    _generation_tasks.add(task)
    task.add_done_callback(_generation_tasks.discard)

    async def stream():
        try:
            while True:
                try:
                    kind, value = await asyncio.wait_for(
                        queue.get(), timeout=KEEPALIVE_INTERVAL_S
                    )
                except TimeoutError:
                    # 무토큰 구간: 클라이언트 watchdog 과 중간 프록시의 idle 판정을 리셋한다.
                    # SSE comment(콜론 시작 줄)는 데이터가 아니라서 클라이언트 파서에 무시된다.
                    yield ": keepalive\n\n"
                    continue
                if kind == "token":
                    yield _sse(value)
                elif kind == "error":
                    # 케이스 4 (업스트림 중단): 연결은 살아 있으므로 에러를 SSE 이벤트로 알린다.
                    payload = json.dumps({"message": value}, ensure_ascii=False)
                    yield f"event: error\ndata: {payload}\n\n"
                    return
                else:
                    yield "data: [DONE]\n\n"
                    return
        except (asyncio.CancelledError, GeneratorExit):
            # 케이스 1 (클라이언트 이탈): 전송만 멈춘다. 생성 task 는 끝까지 돌아 완주 로그를 남긴다.
            print(
                f"client disconnected, streaming stopped (generation continues): message={message!r}",
                flush=True,
            )
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
