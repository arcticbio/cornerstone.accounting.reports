"""Which live test the scripts in this folder act on: the newest, unless CRR_LIVE_TEST names one.

    CRR_LIVE_TEST=2026-09-29 uv run python eval/live/evaluate.py   # re-score the first test

Each test has its own plan (the stakeholders' actions and the predictions, committed before
the test began), its own evidence folder under `eval/reports/`, and its own scratch folder of
generated files under `work/` (never committed).
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
PLANS = {"2026-09-29": "plan", "2026-09-30": "plan_0930"}
NAME = os.environ.get("CRR_LIVE_TEST", "2026-09-30")
if NAME not in PLANS:
    raise SystemExit(f"CRR_LIVE_TEST={NAME!r}: not one of {', '.join(PLANS)}")
plan: ModuleType = importlib.import_module(PLANS[NAME])
OUT = REPO / "eval" / "reports" / f"live-test-{NAME}"
WORK = REPO / "work" / ("livetest" if NAME == "2026-09-29" else f"livetest-{NAME}")
