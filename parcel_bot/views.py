import asyncio
import json

from django.http import HttpRequest, StreamingHttpResponse


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
    message = json.loads(request.body or "{}").get("message", "")

    async def stream():
        async for token in _mock_llm(message):
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(stream(), content_type="text/event-stream")
