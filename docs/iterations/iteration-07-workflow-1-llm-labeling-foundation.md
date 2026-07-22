# Iteration 07: Workflow 1 LLM Labeling Foundation

## Reason

The second-stage division asks workflow 1 to move beyond basic dataset conversion. The group now needs a reproducible way to create a small, useful LLM labeling pool, rather than judging every resume against every job.

## Goal

- Keep workflow 1 as the owner of shared data and evaluation contracts.
- Generate LLM labeling candidate pairs from normalized jobs and resumes.
- Define the LLM label output schema.
- Validate LLM label files before they become gold or high-quality silver labels.

## Changes

Added:

- `scripts/build_llm_label_candidates.py`
  Builds BM25-based candidate pools for LLM labeling. It samples top, middle, and random cross-family jobs per resume.
- `scripts/validate_llm_labels.py`
  Checks LLM label JSONL files for schema issues, duplicate pairs, invalid grades, invalid confidence values, missing evidence, and pairs outside the candidate pool.
- `docs/workflow-1-data-labeling.md`
  Documents the full workflow 1 second-stage process.
- `docs/llm-labeling-guidelines.md`
  Defines grade criteria, evidence rules, hard-constraint handling, and prompt template.

## Current Boundary

This iteration does not call LLM APIs and does not train models. It prepares the files that can be sent to an LLM or human reviewer.

Expected local files:

```text
artifacts/dataset_iteration_05/jobs.jsonl
artifacts/dataset_iteration_05/candidate_profiles.jsonl
artifacts/dataset_iteration_05/llm_label_candidates.jsonl
artifacts/dataset_iteration_05/label_pairs_llm.jsonl
artifacts/dataset_iteration_05/llm_label_quality_report.json
```

## Verification

The new scripts pass Python syntax checks:

```powershell
python -m py_compile .\scripts\build_llm_label_candidates.py .\scripts\validate_llm_labels.py
```

Full data generation requires the raw incoming dataset files to be placed under `dataset/incoming/`.

