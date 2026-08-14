from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent.parent
JOB_UPDATE_ROOT = BACKEND_ROOT / "job_update"
COMPANY_ROOT = JOB_UPDATE_ROOT / "company_job_update"
GOVERNMENT_ROOT = JOB_UPDATE_ROOT / "government_job_update"

for path in (BACKEND_ROOT, JOB_UPDATE_ROOT, COMPANY_ROOT, GOVERNMENT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
