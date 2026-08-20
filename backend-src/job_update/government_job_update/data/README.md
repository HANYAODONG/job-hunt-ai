# Government Job Update Local Data

This directory is reserved for local/generated government job update data.

Expected local files when running the module:

```text
backend-src/job_update/government_job_update/data/base/
  government_initial_job_assignment.csv
  government_job_current_profile_system.csv
  government_job_event_stream.csv
  government_job_event_stream_raw.csv
  government_job_postings_normalized.csv
  government_job_profile_diff.csv
  government_job_profile_snapshots.csv
  government_job_skill_monthly_frequency.csv
  government_job_update.db
  government_skill_job_monthly_spread.csv
  government_skill_lifecycle.csv
  government_skill_migration.csv
  government_skill_pool.csv
  standard_job_title_dictionary.csv

backend-src/job_update/government_job_update/government_jobs_2024_2026_tech_final.csv
```

The full generated CSV/DB files are intentionally not committed to Git because they are large runtime artifacts.
Keep source code, APIs, tests, and documentation in the repository; keep generated data local or distribute it separately.
