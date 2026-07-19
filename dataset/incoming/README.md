# Dataset Incoming Files

This directory is intentionally kept lightweight. Large dataset files are not committed to Git.

Place the following files here before running the dataset adapter:

- `job_bigcompany_final.csv`
- `standard_job_title_dictionary.csv`
- `synthetic_detailed_resumes.csv`
- `resume_job_silver_30.jsonl`
- `金标30×20.csv`

Generate normalized workflow artifacts:

```powershell
python .\scripts\dataset_adapter.py
```

For smoke tests without label files only:

```powershell
python .\scripts\dataset_adapter.py --allow-missing-labels
```

Do not commit raw CSV or JSONL datasets unless the team has explicitly approved data release.
