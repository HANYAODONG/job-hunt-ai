# Canonical L3 Role Admission Gate

## Status

Adopted for the next role-pool expansion round on 2026-08-31.

## Decision

An L3 role is a market-facing functional occupation, not a programming
language, city, employer, business vertical, seniority, or skill bundle. A
candidate role may be activated only after all of the following are recorded:

1. Two independent recruiting sources use a stable title or an unambiguous
   equivalent title. At least one source must be a first-party employer career
   site, a public-sector occupational standard, or a recognized job platform.
2. At least 30 deduplicated, full-text JDs have passed case-by-case review.
3. The candidate has a one-sentence primary deliverable, a core-skill profile,
   and explicit exclusion rules distinguishing it from every nearest active
   role.
4. A 50-case difficult-pair set exists for each nearest-neighbor comparison.
   Two independent reviewers must agree on the mapping before the role may be
   used as matching gold or a graph node.
5. The role-overlap audit does not show an unresolved high-risk neighbor pair.
   Medium-risk pairs require a written boundary decision, not automatic merge.

## Candidate Statuses

- `discovered`: surfaced by title/JD clustering only; never a pool node.
- `market_verified`: has external title evidence; not yet a pool node.
- `validation_ready`: satisfies source/JD-volume requirements and has a
  difficult-pair annotation pack.
- `active`: passed dual review and may be used by graph and matching.
- `specialization_only`: real specialization, but insufficiently distinct for
  its own L3 node; keep it as a tag under an active role.
- `out_of_scope`: a real occupation outside the agreed IT scope.

## Current Implication

The v2 all-review-queue output is a rule-screening artifact, not gold labels.
It cannot activate any L3 role or change the public role count. In particular,
keyword-only hits have produced false positives and must be reviewed against
the complete JD before any use in training or evaluation.

## Owner-Approved Expedited Activation

On 2026-08-31, the product owner approved activation before the normal 30-JD
and 50-case difficult-pair thresholds for these market-verified roles:
`导航定位算法工程师`、`数据科学家`、`安全运营工程师`、`数据中心暖通工程师`、
`游戏技术美术`、`智能硬件产品经理`。 They remain subject to the same primary
deliverable and nearest-neighbor boundaries. Their actual JD assignments must
still pass the strong title or multi-signal rules; the expedited decision does
not authorize keyword-only mappings or turn the v2 screening output into gold.
