# Iteration 13: Frontend Integration Closeout Plan

## Reason

After several workflow PRs were merged, the project already has backend modules for retrieval, semantic reranking, knowledge graph analysis, fusion ranking, resume diagnosis, and JD update. The main remaining risk is no longer a single missing algorithm module, but whether the final frontend can call real backend APIs and present stable results.

One workflow from the previous round, owned by Gan Kexin, is still unfinished. It remains important for enterprise-side job indexing and candidate data outlets, but it should not block the next integration round. The team will continue frontend connection work first and treat that workflow as a carry-over task.

## Purpose

This iteration focuses on making the final frontend usable:

- Verify every main page can open.
- Replace mock data with real backend APIs where possible.
- Record clear backend gaps where real data is not ready.
- Keep the main recommendation chain runnable from the browser.
- Prepare the project for later dynamic graph, model training, and LLM explanation work.

## Main Work

1. Create the fifth-round division document:

```text
docs/分工5.md
```

2. Reframe the next stage around frontend pages instead of isolated algorithm modules.

3. Keep Gan Kexin's unfinished BM25/job-index/export work as a carry-over task.

4. Make Ji Yuhan responsible for frontend API mapping and page-level testing.

5. Assign dynamic graph, learning-path, semantic model, JD update, and backend coordination work around the final frontend pages.

## Expected Outcome

At the end of this iteration, the project should have:

- A deployable main branch.
- A clear frontend-backend API status table.
- A usable recommendation demo page.
- A diagnosis/search/recommendation path backed by real APIs where possible.
- Explicit documentation for pages that still use mock data.
- A concrete path toward dynamic graph and LLM-enhanced explanation.

## Files Added

```text
docs/分工5.md
docs/iterations/iteration-13-frontend-integration-closeout.md
```
