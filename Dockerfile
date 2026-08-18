FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /workspace

# Keep the environment outside /workspace so the bind mount used by Compose
# cannot hide dependencies installed at image-build time.
COPY pyproject.toml uv.lock /tmp/agnostik/
RUN cd /tmp/agnostik && uv sync --frozen --no-dev --no-install-project

CMD ["bash"]
