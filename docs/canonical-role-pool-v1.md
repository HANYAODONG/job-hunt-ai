# Canonical Role Pool v1

This is a reviewed enterprise-only **core** projection of the data group's `job_bigcompany_final.csv`, not a complete market role catalogue. It has 7 first-level domains, 20 second-level directions and 69 defined third-level role identities. The snapshot activates 67 market-facing roles; two catch-all identities remain review-only. Language labels such as Java, Go and Python are specializations of the market-facing `后端开发工程师` role rather than competing third-level roles.

Every active third-level display name must be a market-recognizable job title. Abstract catch-all labels such as `算法工程师（待细分）` and `软件开发工程师（待细分）` are review-only: they may explain an unresolved source label but cannot appear in the formal graph or matching target pool.

Build from a data-group snapshot with:

```powershell
python .\scripts\build_canonical_role_pool.py `
  --input <data-group-repository>\dataset\岗位数据流生成与评测系统\data\input\job_bigcompany_final.csv `
  --output-dir .\artifacts\canonical_role_pool_v1\data_group_current
```

The builder records the source checksum, emits `canonical_jobs.jsonl` for accepted records, and places ambiguous or conflicting records in `role_mapping_review.jsonl`. Only the accepted file may be activated:

```powershell
$env:JOB_HUNT_CANONICAL_ROLE_POOL_PATH = ".\artifacts\canonical_role_pool_v1\data_group_current\canonical_jobs.jsonl"
```

Government and legacy evaluation records are intentionally excluded. They need their own source mappings and skill evidence before becoming part of the canonical pool. The current data-group snapshot and checksums are recorded in `backend-src/app/data/canonical_role_pool/v1/source_snapshot.json`.

## Activation contract

The environment variable changes the graph and matching job source to the accepted
enterprise projection. Its 10,964 records all have `role_mapping_status=mapped`;
they currently exercise 65 of the 67 active identities in the 69-row core
catalog. The remaining two identities are review-only catch-all labels, not
production roles. The 1,656 ambiguous or contradictory records remain in the
review queue and must not be added merely to raise coverage.

Candidate `target_job_family` values remain in the data provider's source-label
space. At scoring time they are mapped to canonical role IDs before comparison.
Equivalent labels such as Java, Go, and backend engineering therefore compare as
the same role. Only the explicit pairs in `role_neighbors.csv` receive partial
credit; career-adjacent roles receive no automatic role credit.

The existing three-channel fusion artifact was built against the old mixed-pool
taxonomy. It is intentionally bypassed whenever a mapped canonical job is used.
Rebuild that artifact with canonical role IDs and this snapshot checksum before
re-enabling fusion for the new pool.

## Production gate

Do not make this the default source until the review queue is adjudicated, the
market-name audit is complete, and a versioned gold set of at least 100 JD-to-role
cases, including adjacent-role and wrong-source-label cases, has passed the target
evaluation. The current opt-in environment variable keeps that migration
reversible. Expansion beyond this source-bounded core must add evidence-backed
market roles rather than inventing more abstract labels.

## Existing Labels And Review Pack

`artifacts/dataset_iteration_05/label_pairs_gold.jsonl` contains 600
resume-to-JD relevance grades, not JD-to-role classifications. Its job IDs have
no overlap with the current accepted enterprise projection, so it must not be
used to claim role-pool accuracy.

Use the following command to prepare a separate, reviewer-owned role-mapping
gold-candidate pack from the current data-group snapshot:

```powershell
python .\scripts\build_role_mapping_gold_candidates.py
```

The generated candidates deliberately leave `final_canonical_role_id`,
`review_decision`, and evidence fields blank. A reviewer must accept, replace,
exclude, or nominate a new-role candidate before a row becomes gold. The
corresponding `existing_matching_gold_audit.json` records which legacy matching
labels can be reconciled later.
