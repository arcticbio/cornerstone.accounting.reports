# syntax=docker/dockerfile:1
#
# Cornerstone Report Runner (SPEC §14).
#
# The image never contains data/bundle/ — that is tenant data and a test fixture, not part of
# the product (SPEC §16, D-08). In-container tests mount the checkout and set CRR_BUNDLE_ROOT.

# ---------------------------------------------------------------------------- builder ----
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first: they change far less often than the source, so this layer caches.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------------------- runtime ----
FROM python:3.12-slim AS runtime

# OCR toolchain (SPEC §14). osd is the orientation model --rotate-pages needs; without it
# ocrmypdf fails at run time on exactly the scanned documents that need it most.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-osd \
        ocrmypdf \
        ghostscript \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin crr

WORKDIR /app
COPY --from=builder --chown=crr:crr /app/.venv /app/.venv
COPY --from=builder --chown=crr:crr /app/src /app/src
COPY --chown=crr:crr config/ /app/config/
COPY --chown=crr:crr eval/golden/ /app/eval/golden/

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CRR_WORK_DIR=/work

RUN mkdir -p /work && chown crr:crr /work
VOLUME ["/work"]

USER crr

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD ["crr", "version"]

ENTRYPOINT ["crr"]
CMD ["--help"]
