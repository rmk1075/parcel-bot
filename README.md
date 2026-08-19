# parcel-bot

배송 접수 챗봇 데모. AI agent 블로그 시리즈의 공용 예제 프로젝트로, 글이 진행될 때마다 확장된다.

- **v0.1** — SSE 스트리밍 chat endpoint + mock LLM. WSGI(runserver)와 ASGI(uvicorn)의 스트리밍 동작 차이 재현.
- **v0.2** — LangGraph 연동. iterator 종류(sync/async) × 서버(WSGI/ASGI) 조합별 버퍼링 매트릭스 재현.
- **v0.3** — 스트리밍 중단 케이스 재현. 채팅 페이지(`/`)와 클라이언트 watchdog, 서버 disconnect 감지, 업스트림 에러 주입.

## 스트리밍 중단 케이스 (v0.3)

| 케이스 | 재현 방법 | 클라이언트가 받는 신호 |
|---|---|---|
| 클라이언트 이탈 | 페이지 닫기 또는 curl 강제 종료 | (서버가 감지: `client disconnected` 로그, 스트림 취소) |
| 서버 종료 | 스트리밍 중 `docker stop parcel-bot-asgi` | 연결 닫힘 (curl exit 18), `[DONE]` 없음 |
| 조용한 절단 | 스트리밍 중 `docker pause parcel-bot-asgi` | 없음. 클라이언트 타임아웃(watchdog)만이 감지 수단 |
| 업스트림 중단 | 메시지에 "오류" 포함해 전송 | `event: error` SSE 이벤트 |

## Endpoints

| Endpoint | 스트림 종류 | WSGI (:8000) | ASGI (:8001) |
|---|---|---|---|
| `POST /chat/` | async generator (mock LLM) | 통째 버퍼링 | 실시간 스트리밍 |
| `POST /graph/sync/` | `graph.stream()` sync generator | 실시간 스트리밍 | 통째 버퍼링 |
| `POST /graph/async/` | `graph.astream()` async generator | 통째 버퍼링 | 실시간 스트리밍 |
| `POST /graph/bridge/` | sync stream 을 per-item `sync_to_async(next)` 로 감싼 async generator | — | 실시간 스트리밍 |

iterator 종류와 서버 종류가 어긋나면 Django 가 스트림을 통째로 소비한 뒤 한 번에 내보낸다.

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
