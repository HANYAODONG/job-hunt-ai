# Iteration 06: Workflow 4 Fusion Ranking Integration

## Reason

After workflows 1, 2, 3, and 5 had been merged, PR #1 for workflow 4 still needed to be integrated into the latest `main`. Its original branch was based on an older project state, so the main risk was preserving existing BM25, BGE semantic reranking, and KG routes while adding fusion ranking.

## Goal

- Merge workflow 4 into `main`.
- Keep all existing backend routes intact.
- Add a frontend demo entry for fusion ranking.
- Record the output contract for later real BM25/BGE/KG integration.

## Merged Content

Backend:

- `backend-src/app/models/fusion.py`
  Defines fusion input/output models, including `bm25_score`, `semantic_score`, `skill_coverage`, `job_family_match`, `graph_relatedness`, `missing_skills`, and `evidence_paths`.
- `backend-src/app/services/fusion_scoring_service.py`
  Implements weighted fusion scoring, ranking, rule-based explanations, and mock input generation.
- `backend-src/app/api/endpoints/fusion.py`
  Adds `/api/v1/fusion/score`, `/api/v1/fusion/rank`, `/api/v1/fusion/mock-rank`, and weight management endpoints.
- `backend-src/app/main.py`
  Registers the fusion router while preserving existing jobs, ingestion, reranking, KG, BM25, semantic, auth, and keyword extraction routers.

Frontend:

- `frontend-src/src/pages/FusionDemoPage.js`
  Adds a standalone fusion demo page.
- `frontend-src/src/components/FusionScoreCard.js`
  Adds a fusion score card with factor breakdown and explanations.
- `frontend-src/src/services/fusionApi.js`
  Adds fusion API calls and local mock fallback.
- `frontend-src/src/data/mockFusionData.js`
  Adds frontend-side mock fusion data generation.
- `frontend-src/src/App.js`
  Registers `/fusion-demo`.
- `frontend-src/src/setupProxy.js`
  Proxies `/api` requests only, so React Router can handle `/fusion-demo`.

## Adjustment After Merge

- Removed unused imports/state in the fusion API endpoint and demo page to reduce build warnings.
- Kept BM25 raw score compatibility. Workflow 5 may produce BM25 scores greater than 1, so fusion-side integration should normalize BM25 before final production scoring or clearly pass a normalized BM25 field.

## Current Integration Boundary

Workflow 4 can now run in mock mode independently. For real integration, it should read:

- BM25 candidates from `artifacts/bm25/bm25_top200.jsonl`.
- BGE semantic scores from `artifacts/semantic_index/semantic_rerank_output.jsonl`.
- KG features from `artifacts/kg/`.

Recommended final output location:

- `artifacts/fusion/fusion_rankings.jsonl`
- `artifacts/fusion/fusion_explanations.jsonl`

## Verification

- Backend fusion files pass `python -m py_compile`.
- Frontend fusion JS files pass `node --check`.

