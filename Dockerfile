FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

# 의존성 레이어 분리 — 코드만 바뀌면 uv sync 캐시 재사용
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "parcel_bot.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
