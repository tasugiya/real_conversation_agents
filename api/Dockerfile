# Build context is the repository root (docker build -f api/Dockerfile .),
# not api/, so that a future need to COPY packages/shared-schemas/ stays
# straightforward. See .dockerignore at the repo root.

FROM python:3.12-slim

# Official recommended pattern: copy the static uv binary rather than
# installing it via pip (https://docs.astral.sh/uv/guides/integration/docker/).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copied separately from src/ so dependency install is cached even when only
# application code changes.
COPY api/pyproject.toml ./pyproject.toml
RUN uv pip install --system -r pyproject.toml

COPY api/src ./src

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
