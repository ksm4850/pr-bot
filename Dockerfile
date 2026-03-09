FROM python:3.12-slim

# git + node (Claude Code CLI)
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /uvx /usr/local/bin/

WORKDIR /app

# 의존성 먼저 복사 → 캐시 활용
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# 소스 복사
COPY app/ app/

# data 디렉토리 (마운트 포인트)
RUN mkdir -p /app/data
VOLUME /app/data

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]