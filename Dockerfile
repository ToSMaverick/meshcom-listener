# Stage 1: Build stage
FROM ghcr.io/astral-sh/uv:python3.13-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Install dependencies (cached)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Stage 2: Final stage (Das reine Runtime-Image)
FROM python:3.13-slim-bookworm
WORKDIR /app

# Copy the installed packages from the builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application code
COPY . .

# Security: Run as non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# UDP Port for MeshCom
EXPOSE 1799/udp

# Standard-Kommando
ENTRYPOINT ["python", "main.py"]
CMD ["serve"]
