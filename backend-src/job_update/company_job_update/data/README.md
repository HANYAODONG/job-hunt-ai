# Company Job Update Local Data

This directory is reserved for local/generated company job update data.

Expected local structure when running the module:

```text
backend-src/job_update/company_job_update/data/versions/<version_name>/
  job_current_profile_system.csv
  job_profile_diff.csv
  job_profile_snapshots.csv
  job_skill_monthly_frequency.csv
  job_update.db
  job_update_event_stream.csv
  skill_job_monthly_spread.csv
  skill_lifecycle.csv
  skill_migration.csv
  skill_pool.csv
  standard_job_title_dictionary.csv
  version_manifest.json
```

The full generated CSV/DB files are intentionally not committed to Git because they are large runtime artifacts.
Keep source code, APIs, tests, and documentation in the repository; keep generated data local or distribute it separately.
