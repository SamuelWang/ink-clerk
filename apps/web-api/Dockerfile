FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src ./src

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --app-dir src --host 0.0.0.0 --port ${PORT:-8000}"]
