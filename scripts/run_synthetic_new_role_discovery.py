"""Run the isolated new-role discovery fixture from the command line."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-src"))

from app.services.discovery_fixture_service import run_synthetic_new_role_fixture  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(run_synthetic_new_role_fixture(), ensure_ascii=False, indent=2))
