FROM python:3.12-slim AS base
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
COPY uv.lock* .
RUN uv sync --no-dev || uv sync --no-frozen --no-dev
# Make uv-installed binaries available on PATH
ENV PATH="/app/.venv/bin:$PATH"

FROM base AS development
RUN uv sync || uv sync --no-frozen
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
COPY . .
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
