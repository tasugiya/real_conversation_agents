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

# Cloud Run terminates TLS at its front end and forwards over plain HTTP,
# setting X-Forwarded-Proto/-For. Uvicorn's ProxyHeadersMiddleware only trusts
# 127.0.0.1 by default, so without --forwarded-allow-ips request.base_url stays
# "http://..." -- breaking anything (e.g. Cloud Tasks OIDC targets) that needs
# an https:// URL back to this same service. Trusting '*' is safe here because
# Cloud Run's own front end is the only thing that can reach this container.
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
