# Stage 1: Build stage
FROM ghcr.io/astral-sh/uv:python3.14-trixie AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Install dependencies (cached)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock,relabel=shared \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml,relabel=shared \
    uv sync --frozen --no-install-project --no-dev

# Stage 2: Final stage (Das reine Runtime-Image)
FROM python:3.14-slim-trixie
WORKDIR /app

# 1. Benutzer zuerst anlegen
RUN useradd -m appuser

# 2. Kopieren mit direktem chown (verhindert Layer-Duplizierung)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 3. Code kopieren mit direktem chown
COPY --chown=appuser:appuser . .

# Wechsel zum non-root User
USER appuser

# UDP Port for MeshCom
EXPOSE 1799/udp

# Standard-Kommando
ENTRYPOINT ["python", "main.py"]
CMD ["serve"]
