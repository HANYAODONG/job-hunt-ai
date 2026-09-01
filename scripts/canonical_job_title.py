"""Conservative normalization from noisy JD titles to closed-set labels."""

from __future__ import annotations

import re
from typing import Any


LANGUAGE_PATTERNS = (
    ("Java", re.compile(r"(?i)(?<![a-z])java(?![a-z])")),
    ("Go", re.compile(r"(?i)(?<![a-z])golang(?![a-z])|Go语言")),
    ("Python", re.compile(r"(?i)(?<![a-z])python(?![a-z])")),
    ("C++", re.compile(r"(?i)c\+\+|c／c\+\+")),
    ("Rust", re.compile(r"(?i)(?<![a-z])rust(?![a-z])")),
)


def canonical_job_title(job: dict[str, Any]) -> str:
    """Return the approved display label for a concrete JD.

    The canonical role is the default label. Language-specific backend titles
    remain distinguishable only when the source title explicitly states the
    language; company, city, seniority, and internship suffixes are ignored.
    """
    role_id = str(job.get("canonical_role_id") or "")
    canonical_role = str(job.get("canonical_role") or job.get("standard_job") or job.get("job_family") or "").strip()
    title = str(job.get("title") or "")
    if role_id == "backend_engineering":
        for label, pattern in LANGUAGE_PATTERNS:
            if pattern.search(title):
                return f"{label}{canonical_role or '后端开发工程师'}"
    return canonical_role or "未定规范岗位"

