FROM astral/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-cache
# RUN uv sync --frozen --no-cache --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

CMD ["sh", "-c", "uv run alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]