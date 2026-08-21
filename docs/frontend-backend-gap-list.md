# Frontend-Backend Gap List

Updated after merging PR #15/#16/#17.

## Current Live / Mock Status

| Area | Page / Service | Status | Notes |
| --- | --- | --- | --- |
| Fusion recommendation | `/fusion-demo`, `fusionApi.recommendJobs` | live | Calls `POST /api/v1/fusion/recommend`; keeps offline/mock modes for fallback. |
| Resume diagnosis | `/diagnosis`, `talentApi.diagnoseCandidate` | live with fallback | Intended chain: resume upload -> BM25 -> semantic rerank -> KG gap -> fusion rank. Falls back to legacy recommendations if the full chain fails. |
| BM25 retrieval | `intelligenceApi.searchBm25` | live | Calls `/api/v1/bm25/search`. |
| Semantic rerank | `intelligenceApi.rerankSemantic` | live | Calls `/api/v1/semantic/rerank`. |
| KG gap analysis | `intelligenceApi.analyzeKnowledgeGraphGap` | live | Calls `/api/v1/kg/analyze`; requires job_id/candidate_id alignment. |
| Market CSV ingestion | `talentApi.importMarketCsv` | live | Calls CSV ingestion API. |
| Market runtime stats | `talentApi.getMarketRuntimeStatus` | partial-live | Uses backend stats, but trend candidates are still mock. |
| Graph visualization | `/graph`, `getCapabilityGraph` | mock-only | Needs real nodes/edges graph API. |
| Learning plan | `/learning`, `getLearningPlan` | mock-only | Needs learning-path generation API. |
| Recruitment jobs | `/recruitment`, `getRecruitmentJobs` | live with fallback | Reads 12,675 enterprise jobs and supports runtime detail/status edits through `/api/v1/talent/jobs`. |
| Candidate pipeline | `/candidates`, `getJobCandidates` | live with fallback | Reads 30,200 candidate profiles, returns explainable baseline scores, and persists candidate stages through `/api/v1/talent/jobs/{job_id}/candidates`. |
| Dashboard overview | `/`, `getTalentOverview` | mock-only | Needs aggregate dashboard API if required for final demo. |
| Governance / evaluation | `/governance`, `/evaluation` | mock-only | Low priority unless final frontend keeps these pages. |

## Page-Level Gaps

### `/fusion-demo`

Already connected to `POST /api/v1/fusion/recommend`.

Remaining work:

- Run browser-level verification after Docker/Node environment is available.
- Confirm result cards show `final_score`, `score_breakdown`, matched skills, missing skills, and explanation.

### `/diagnosis`

Partially connected to the real backend chain.

Remaining work:

- Verify actual resume upload flow on the new machine.
- Confirm BM25 job IDs, KG job IDs, and fusion job IDs are aligned.
- Improve empty/error states when one backend stage is unavailable.

### `/graph`

Still mock-only.

Needed backend output:

```json
{
  "nodes": [],
  "edges": [],
  "snapshot_id": "2026",
  "metadata": {}
}
```

Each node should include id, label, type, weight/count, and optional year. Each edge should include source, target, relation, and weight.

### `/learning`

Still mock-only.

Needed backend output:

```json
{
  "target_role": "...",
  "missing_skills": [],
  "stages": [],
  "resources": []
}
```

This can be generated from diagnosis gaps plus optional LLM explanation later.

### `/recruitment`

Connected to the artifact-backed talent API with mock fallback.

- Job list, detail, skill requirements, source, and update timestamp come from the standardized enterprise dataset.
- Runtime edits and status updates are supported, but are not written back to the source dataset.
- The JD update module remains available independently for incremental update workflows.

### `/candidates`

Connected to the artifact-backed talent API with mock fallback.

- Candidate list, matched/missing skills, screening reason, and stage update are available.
- Current ranking is an explainable baseline: skill overlap 65%, role-family/category consistency 25%, and experience 10%.
- Replace the baseline with BM25, BGE-M3, Neo4j, and Fusion results after their IDs and score contracts are aligned.

### `/signals`

Partial-live.

Already can use backend stats/CSV ingestion, but discovery candidates and market-change candidates still come from mock data.

The new JD update module may become the backend source for market signals after its API contract is mapped to the frontend.

## Legacy Pages

The old pages remain available:

- `/search`
- `/recommendations`
- `/personalized-recommendations`
- `/upload-resume`
- `/job/:jobId`

They still use older search/recommendation APIs. Do not migrate all of them at once. Prefer finishing the new workbench pages first.

## Priority

1. Verify `/fusion-demo` with real backend.
2. Verify `/diagnosis` full chain with uploaded resume.
3. Wire `/signals` to the new JD update module where possible.
4. Add real graph API for `/graph`.
5. Replace the candidate baseline with aligned BM25, BGE-M3, Neo4j, and Fusion results.
6. Add learning-path API for `/learning`.
