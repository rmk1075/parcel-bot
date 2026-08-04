# parcel-bot

배송 접수 챗봇 데모. AI agent 블로그 시리즈의 공용 예제 프로젝트로, 글이 진행될 때마다 확장된다.

- **v0.1** — SSE 스트리밍 chat endpoint + mock LLM. WSGI(runserver)와 ASGI(uvicorn)의 스트리밍 동작 차이 재현.

LLM은 호출하지 않는다 — 고정 답변을 토큰 단위로 흘리는 mock이라 API key 없이 재현된다.

## 실행

```bash
uv sync

# WSGI — 전부 버퍼링됐다가 한 번에 도착한다
uv run python manage.py runserver

# ASGI — 토큰이 실시간으로 도착한다
uv run uvicorn parcel_bot.asgi:application
```

## 확인

```bash
curl -sN -X POST http://127.0.0.1:8000/chat/ -d '{"message":"책 보내려고요"}' \
  | while IFS= read -r line; do [ -n "$line" ] && echo "$(date +%S.%3N) $line"; done
```

왼쪽 타임스탬프로 도착 간격을 본다. runserver는 모든 줄이 같은 시각(서버가 다 만든 뒤 통째로 flush), uvicorn은 300ms 간격.

## 테스트

```bash
uv run python manage.py test
```
