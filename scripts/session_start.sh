#!/usr/bin/env bash
# Runs at the start of every Claude Code session (cloud and local). Must exit 0.
set -u
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

echo "== crr session start =="
if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
  uv sync --frozen >/dev/null 2>&1 && echo "uv sync: ok" || echo "uv sync: FAILED (run manually and inspect)"
else
  echo "uv sync: skipped (no pyproject.toml yet — Phase 0 creates it)"
fi

for tool in tesseract ocrmypdf gs; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "$tool: $($tool --version 2>&1 | head -1)"
  else
    echo "$tool missing (tesseract missing) — install with: apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd ocrmypdf ghostscript"
  fi
done

[ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY: set" || echo "ANTHROPIC_API_KEY: not set (classifier phases degrade to golden)"
[ -n "${GOOGLE_SERVICE_ACCOUNT_B64:-}" ] && echo "GOOGLE_SERVICE_ACCOUNT_B64: set" || echo "GOOGLE_SERVICE_ACCOUNT_B64: not set (Drive phase uses fake)"
[ -n "${CRR_GDRIVE_ROOT_FOLDER_ID:-}" ] && echo "CRR_GDRIVE_ROOT_FOLDER_ID: set" || echo "CRR_GDRIVE_ROOT_FOLDER_ID: not set"

echo
echo "== PROGRESS.md (top) =="
head -40 PROGRESS.md 2>/dev/null || echo "(no PROGRESS.md)"
exit 0
