# Dataset Incoming Files

This directory only keeps the local dataset placement guide. Large CSV, JSONL, and Markdown dataset files are not committed to Git.

Before local deployment or dataset conversion, place these files here:

- `job_bigcompany_final.csv`
- `standard_job_title_dictionary.csv`
- `synthetic_detailed_resumes.csv`
- `resume_job_silver_30.jsonl`
- `金标30×20.csv`
- `金银标区别.md`

Then generate normalized workflow artifacts:

```powershell
python .\scripts\dataset_adapter.py
```

For smoke tests without label files only:

```powershell
python .\scripts\dataset_adapter.py --allow-missing-labels
```

Do not commit raw CSV, JSONL, or dataset Markdown files unless the team has explicitly approved data release.
