# --- Node build stage (Vue SPA) ---
FROM node:22-slim AS spa-build
WORKDIR /build/web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ .
RUN npm run build

# --- Python build stage ---
# Build context is src/nupla/app/; we install from the root pyproject.toml.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS py-build
WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project
COPY README.md ./
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev || uv sync --no-dev

# --- Runtime stage ---
FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r app && useradd -r -g app -u 1001 app

COPY --from=py-build /app/.venv /app/.venv
COPY --from=py-build /app/src /app/src
COPY --from=spa-build /build/web/dist /app/web/dist

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    WEB_DIST="/app/web/dist"

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -fsS http://localhost:8080/api/health || exit 1

CMD ["uvicorn", "nupla.app.server:app", "--host", "0.0.0.0", "--port", "8080"]
