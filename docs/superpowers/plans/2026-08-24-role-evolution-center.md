# Role Evolution Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将第二仓库的四项核心岗位技能演化能力组织到第一个仓库企业端 `/signals` 的“岗位演化中心”，保持主系统现有视觉体系并提供可观察、可操作的完整工作流。

**Architecture:** 保留第一个仓库的 React 工作台、Ant Design 控件和 `TechnicalInspector` 证据面板；用岗位演化中心作为单一企业端入口，通过四个内部视图承载 JD 更新、实时演化、时序分析和人工优化。服务层先维持 mock-first 契约，并为第二仓库的 `/api/jobs/*`、`/api/analytics/*`、`/api/optimization/*` 和 `/api/live-evolution/*` 建立适配边界，避免把独立静态控制台直接嵌入主系统。

**Tech Stack:** React 18, React Router 6, Ant Design 5, existing workbench CSS, Jest/React Testing Library.

## Global Constraints

- 只接入四项核心能力：单条 JD 更新、实时岗位演化、时序分析、人工优化。
- 数据流测试、备份记录和独立数据源调试控件不进入主导航。
- 页面遵循第一个仓库的清晰、简洁、证据优先设计，不复制第二仓库的独立 HTML/CSS。
- 结论先展示，证据、来源和处理记录按需展开。
- 保留现有 mock fallback，真实后端不可用时页面仍可展示可验证示例。

### Task 1: Define the role-evolution service contract

**Files:**
- Modify: `frontend-src/src/services/talentApi.js`
- Modify: `frontend-src/src/services/talentApi.test.js`
- Test: `frontend-src/src/services/talentApi.test.js`

**Interfaces:**
- Produce `getRoleEvolutionWorkspace()` returning `{ jobs, pending, latest, analytics, optimization }`.
- Produce `submitRoleJd(payload)`, `getLiveEvolution(effectId)`, `getRoleAnalytics(params)`, and `saveRoleOptimization(payload)`.
- Each function must preserve the existing mock fallback and normalize empty backend responses into stable arrays/objects.

- [ ] Add tests for stable workspace shape and mutation payload normalization.
- [ ] Run the focused service tests and verify the new tests fail before implementation.
- [ ] Implement adapters using existing API helpers and `mockTalentData` fallback data.
- [ ] Re-run the focused service tests and verify all pass.

### Task 2: Build the four-view role evolution center

**Files:**
- Create: `frontend-src/src/pages/RoleEvolutionCenterPage.js`
- Create: `frontend-src/src/pages/RoleEvolutionCenterPage.css`
- Modify: `frontend-src/src/App.js`
- Modify: `frontend-src/src/components/workbench/WorkbenchLayout.js`

**Interfaces:**
- Route `/signals` to `RoleEvolutionCenterPage`.
- Keep `/discovery` and `/evolution` as aliases to `/signals`.
- Internal view keys are `jd-update`, `live-evolution`, `analytics`, and `optimization`.

- [ ] Add page-level render tests for the four view labels and default JD update state.
- [ ] Implement a compact internal tab bar with one primary action and a persistent selected-role context.
- [ ] Implement JD form/result, live evolution summary, analytics panels, and optimization editor using Ant Design and `TechnicalInspector`.
- [ ] Add loading, empty, error, saved, and published states without exposing debug-only pages.
- [ ] Run page tests and verify the four views remain usable at narrow widths.

### Task 3: Connect existing evidence and graph workflows

**Files:**
- Modify: `frontend-src/src/pages/GraphPage.js`
- Modify: `frontend-src/src/pages/DiagnosisPage.js`
- Modify: `frontend-src/src/services/talentApi.js`

**Interfaces:**
- Published role optimization must expose the selected role/version for graph and diagnosis links.
- Live evolution results must link to `/graph` and `/diagnosis` without losing role/version context.

- [ ] Add tests for role/version navigation state.
- [ ] Add contextual links from the center to the existing graph and diagnosis pages.
- [ ] Keep graph and diagnosis behavior unchanged when no role-evolution context exists.
- [ ] Run existing graph, diagnosis, and service tests.

### Task 4: Verify build and visual behavior

**Files:**
- Modify: `frontend-src/src/components/workbench/workbench.css` only if a scoped layout correction is required.

- [ ] Run `npm test -- --watchAll=false` in `frontend-src`.
- [ ] Run `npm run build` in `frontend-src`.
- [ ] Start the frontend dev server on an available port and verify `/signals` in desktop and narrow viewport states.
- [ ] Confirm no debug-only navigation items were added and no existing untracked user files were changed.

