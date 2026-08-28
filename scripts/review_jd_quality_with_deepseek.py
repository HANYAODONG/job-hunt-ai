"""Compatibility entry point for the phase-6 DeepSeek JD review."""

from __future__ import annotations

import runpy
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "backend-src"
    / "scripts"
    / "review_jd_quality_with_deepseek.py"
)


if __name__ == "__main__":
    runpy.run_path(str(SCRIPT), run_name="__main__")
