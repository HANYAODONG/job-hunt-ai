from __future__ import annotations

from pathlib import Path

from job_update.company_job_update.core.data_versions import resolve_company_data_paths


APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = APP_ROOT.parent
DATASET_ROOT = BACKEND_ROOT
JOB_UPDATE_ROOT = BACKEND_ROOT / "job_update"
JOB_UPDATE_GROUP_ROOT = JOB_UPDATE_ROOT
COMPANY_JOB_UPDATE_ROOT = JOB_UPDATE_ROOT / "company_job_update"
GOVERNMENT_JOB_UPDATE_ROOT = JOB_UPDATE_ROOT / "government_job_update"
SKILL_EXTRACT_ROOT = COMPANY_JOB_UPDATE_ROOT / "skill_extract"
SKILL_ALIAS_DICTIONARY = SKILL_EXTRACT_ROOT / "company_skill_dictionary.csv"
SKILL_NORMALIZED_DICTIONARY = SKILL_ALIAS_DICTIONARY
SKILL_DISPLAY_DICTIONARY = SKILL_ALIAS_DICTIONARY

COMPANY_DATA_PATHS = resolve_company_data_paths()
BASE_DATA_DIR = COMPANY_DATA_PATHS.data_dir
BASE_DATABASE = COMPANY_DATA_PATHS.database
BASE_TITLE_DICTIONARY = COMPANY_DATA_PATHS.title_dictionary
BASE_EVENT_STREAM = COMPANY_DATA_PATHS.event_stream
BASE_FREQUENCY_OUTPUT = COMPANY_DATA_PATHS.frequency
BASE_SKILL_POOL = COMPANY_DATA_PATHS.skill_pool
BASE_SKILL_LIFECYCLE = COMPANY_DATA_PATHS.lifecycle
BASE_SKILL_MIGRATION = COMPANY_DATA_PATHS.migration
BASE_SKILL_MONTHLY_SPREAD = COMPANY_DATA_PATHS.spread
BASE_JOB_PROFILE_DIFF = COMPANY_DATA_PATHS.profile_diff
BASE_JOB_PROFILE_SNAPSHOTS = COMPANY_DATA_PATHS.profile_snapshots
BASE_CURRENT_PROFILE = COMPANY_DATA_PATHS.current_profile

GOVERNMENT_BASE_DATA_DIR = GOVERNMENT_JOB_UPDATE_ROOT / "data" / "base"
GOVERNMENT_BASE_DATABASE = GOVERNMENT_BASE_DATA_DIR / "government_job_update.db"
GOVERNMENT_BASE_TITLE_DICTIONARY = GOVERNMENT_BASE_DATA_DIR / "standard_job_title_dictionary.csv"
GOVERNMENT_BASE_EVENT_STREAM = GOVERNMENT_BASE_DATA_DIR / "government_job_event_stream.csv"
GOVERNMENT_BASE_FREQUENCY_OUTPUT = GOVERNMENT_BASE_DATA_DIR / "government_job_skill_monthly_frequency.csv"
GOVERNMENT_BASE_SKILL_POOL = GOVERNMENT_BASE_DATA_DIR / "government_skill_pool.csv"
GOVERNMENT_BASE_SKILL_LIFECYCLE = GOVERNMENT_BASE_DATA_DIR / "government_skill_lifecycle.csv"
GOVERNMENT_BASE_SKILL_MIGRATION = GOVERNMENT_BASE_DATA_DIR / "government_skill_migration.csv"
GOVERNMENT_BASE_SKILL_MONTHLY_SPREAD = GOVERNMENT_BASE_DATA_DIR / "government_skill_job_monthly_spread.csv"
GOVERNMENT_BASE_JOB_PROFILE_DIFF = GOVERNMENT_BASE_DATA_DIR / "government_job_profile_diff.csv"
GOVERNMENT_BASE_JOB_PROFILE_SNAPSHOTS = GOVERNMENT_BASE_DATA_DIR / "government_job_profile_snapshots.csv"
GOVERNMENT_BASE_CURRENT_PROFILE = GOVERNMENT_BASE_DATA_DIR / "government_job_current_profile_system.csv"

# The historical data-stream generator is intentionally outside this runtime
# module. Formal analytics only read the two domain-owned base datasets.
DATA_STREAM_ROOT = JOB_UPDATE_ROOT / "data_stream"
DATA_STREAM_TITLE_DICTIONARY = DATA_STREAM_ROOT / "data" / "input" / "standard_job_title_dictionary.csv"
DATA_STREAM_SKILL_DICTIONARY = DATA_STREAM_ROOT / "data" / "input" / "company_skill_dictionary_with_type.csv"
BACKUP_ROOT = BACKEND_ROOT / "jd_update_backups"


def resolve_domain(domain: str) -> str:
    value = str(domain or "company").strip().lower()
    if value not in {"company", "government"}:
        raise ValueError("domain must be company or government")
    return value


def domain_file(domain: str, name: str) -> Path:
    domain = resolve_domain(domain)
    files = {
        "company": {
            "frequency": BASE_FREQUENCY_OUTPUT,
            "lifecycle": BASE_SKILL_LIFECYCLE,
            "migration": BASE_SKILL_MIGRATION,
            "spread": BASE_SKILL_MONTHLY_SPREAD,
            "snapshot": BASE_JOB_PROFILE_SNAPSHOTS,
            "diff": BASE_JOB_PROFILE_DIFF,
            "current": BASE_CURRENT_PROFILE,
        },
        "government": {
            "frequency": GOVERNMENT_BASE_FREQUENCY_OUTPUT,
            "lifecycle": GOVERNMENT_BASE_SKILL_LIFECYCLE,
            "migration": GOVERNMENT_BASE_SKILL_MIGRATION,
            "spread": GOVERNMENT_BASE_SKILL_MONTHLY_SPREAD,
            "snapshot": GOVERNMENT_BASE_JOB_PROFILE_SNAPSHOTS,
            "diff": GOVERNMENT_BASE_JOB_PROFILE_DIFF,
            "current": GOVERNMENT_BASE_CURRENT_PROFILE,
        },
    }
    try:
        return files[domain][name]
    except KeyError as exc:
        raise ValueError(f"Unknown domain file: {domain}/{name}") from exc
