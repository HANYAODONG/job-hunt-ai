import {
  dashboardData,
  diagnosisData,
  discoveryCandidates,
  evaluationData,
  evolutionData,
  governanceData,
  learningPlanData,
  marketChangeCandidates,
  roleCatalogData,
} from '../data/mockTalentData';
import { recruitmentCandidatesData, recruitmentJobsData } from '../data/mockRecruitmentData';
import {
  getJobById,
  getJobRecommendations,
  getMarketTrends,
  searchJobsWithResume,
  uploadResume,
} from './api';
import {
  analyzeKnowledgeGraphGap,
  generateLearningPlan,
  getMarketRuntime,
  getTalentCandidates,
  getTalentCandidateExplanation,
  getTalentJobs,
  getTalentMarketStats,
  ingestMarketCsv,
  patchTalentCandidateStage,
  putTalentJob,
  rankRoleAware,
  rerankSemantic,
  searchBm25,
} from './intelligenceApi';
import { rankJobs } from './fusionApi';

export const TALENT_API_CAPABILITIES = Object.freeze({
  resumeDiagnosis: 'live',
  bm25Retrieval: 'live',
  semanticReranking: 'live',
  knowledgeGraphGap: 'live',
  fusionRanking: 'live',
  roleAwareMatching: 'live-with-fallback',
  capabilityGraph: 'live-with-canonical-fallback',
  learningPlan: 'live-with-fallback',
  recruitment: 'live-with-fallback',
  candidatePipeline: 'live-with-fallback',
  marketSignals: 'partial-live',
  marketDataIngestion: 'live',
  governance: 'mock-only',
  evaluation: 'mock-only',
});

const mockOnly = async (fallback) => fallback;

export const getTalentOverview = () => mockOnly(dashboardData);

const normalizeDiscoveryReview = (item) => {
  if (item?.candidate_id) {
    const source = item.source || {};
    const definition = item.definition || {};
    const skills = (item.skills || []).map(skillName).filter(Boolean);
    const routeScore = Number(item.candidate_jobs?.[0]?.score || 0);
    const stageStatus = item.stage === 'published'
      ? '已发布'
      : item.stage === 'awaiting_publish'
        ? '待正式发布'
        : '待审核';
    return {
      id: item.candidate_id,
      maintenanceId: item.maintenance_id || '',
      stage: item.stage || 'candidate',
      name: source.job_title || item.title || '未命名岗位候选',
      status: stageStatus,
      confidence: Math.round(Math.max(0, Math.min(1, routeScore)) * 100),
      evidence: Number(item.source_count || 1),
      sourceCount: Number(item.source_count || 1),
      sources: [{
        source: '原始 JD 审核队列',
        confidence: '原始 JD',
        excerpt: source.responsibility || source.requirement || '未提供职责或要求',
        collectedAt: source.month || item.updated_at || '本地审核记录',
      }],
      signals: [item.route_reason || '岗位与现有标准岗位边界不清', source.requirement || '未提供岗位要求'],
      skills,
      domain: item.best_category || '待归类',
      updatedAt: item.updated_at || source.month || '',
      version: item.stage === 'published' ? '正式岗位 v1.0' : '候选定义 v0.1',
      routeStatus: item.route_status || 'potential_new_job',
      definition: {
        coreResponsibilities: definition.core_responsibilities || [],
        requiredSkills: definition.required_skills || skills,
        bonusSkills: definition.bonus_skills || [],
        scenarios: definition.application_scenarios || [],
        evidenceNote: definition.evidence_note || '由原始 JD 证据生成，发布前需人工核验。',
      },
      raw: item,
    };
  }
  const route = item?.result?.route || {};
  const source = item?.input || {};
  const bestScore = Number(route.best_job?.score ?? route.best_category?.score ?? 0);
  const skills = (item?.result?.skills || []).map(skillName).filter(Boolean);
  const definition = item?.result?.definition || {};
  return {
    id: item?.item_id,
    name: source.job_title || item?.result?.job_title || '未命名岗位候选',
    status: item?.status === 'submitted_dictionary_maintenance' ? '待正式发布' : '待审核',
    confidence: Math.round(Math.max(0, Math.min(1, bestScore)) * 100),
    evidence: 1,
    sourceCount: 1,
    sources: [{
      source: source.source || 'JD 审核队列',
      confidence: '原始 JD',
      excerpt: source.responsibility || source.requirement || '未提供职责或要求',
      collectedAt: source.month || item?.updated_at || '本地审核记录',
    }],
    signals: [route.reason || '岗位与现有标准岗位边界不清', source.requirement || '未提供岗位要求'],
    skills,
    domain: route.best_category?.name || '待归类',
    updatedAt: item?.updated_at || item?.created_at || source.month || '',
    version: '候选定义 v0.1',
    routeStatus: route.status || 'potential_new_job',
    definition: {
      coreResponsibilities: definition.core_responsibilities || [],
      requiredSkills: definition.required_skills || skills,
      bonusSkills: definition.bonus_skills || [],
      scenarios: definition.application_scenarios || [],
      evidenceNote: definition.evidence_note || '由原始 JD 证据生成，发布前需人工核验。',
    },
    raw: item,
  };
};

export const getDiscoveryCandidates = async () => {
  if (!roleEvolutionLiveEnabled) return discoveryCandidates;
  try {
    const rows = await roleEvolutionRequest(roleEvolutionPath(
      '/jd-update/discovery/candidates?domain=company',
      '/api/discovery/candidates?domain=company',
    ));
    return (Array.isArray(rows) ? rows : [])
      .filter((item) => item?.candidate_id || (item?.review_type === 'job' && item?.result?.route?.status !== 'existing_job'))
      .map(normalizeDiscoveryReview);
  } catch {
    return discoveryCandidates;
  }
};

export const getDiscoveryBatch = async (month = '', threshold = 10, standardJob = '') => {
  if (!roleEvolutionLiveEnabled) {
    const candidates = discoveryCandidates.map((item) => item?.candidate_id || item?.result ? normalizeDiscoveryReview(item) : item);
    return {
      month: month || '演示批次',
      available_months: [],
      input_jd_count: 0,
      deduplicated_jd_count: 0,
      unmapped_jd_count: candidates.length,
      cluster_count: candidates.length,
      trigger_threshold: threshold,
      threshold_rule: '去重后的同类 JD 数量 > 10，且需保留来源证据后进入人工审核',
      method: '前端回退候选（仅演示）',
      candidates: candidates.map((candidate, index) => ({
        cluster_id: `DEMO-${index + 1}`,
        title: candidate.name,
        supporting_jd_count: candidate.evidence || 0,
        deduplicated_jd_count: candidate.evidence || 0,
        source_count: candidate.sourceCount || 1,
        threshold,
        threshold_met: (candidate.evidence || 0) > threshold,
        status: candidate.status || '观察中',
        workflow_stage: candidate.status || '待审核',
        candidate,
        evidence: [candidate],
      })),
      guardrails: ['候选聚类不会自动写入正式岗位池', '正式三级岗位必须经过人工复核并分配 canonical_role_id'],
    };
  }
  try {
    const query = new URLSearchParams({ domain: 'company', threshold: String(threshold) });
    if (month) query.set('month', month);
    if (standardJob) query.set('standard_job', standardJob);
    return await roleEvolutionRequest(roleEvolutionPath(
      `/jd-update/discovery/batch?${query.toString()}`,
      `/api/discovery/batch?${query.toString()}`,
    ));
  } catch {
    const candidates = await getDiscoveryCandidates();
    return {
      month: month || '', available_months: [], input_jd_count: 0, deduplicated_jd_count: 0,
      unmapped_jd_count: candidates.length, cluster_count: candidates.length,
      trigger_threshold: threshold, threshold_rule: '去重后的同类 JD 数量 > 10，且需保留来源证据后进入人工审核',
      method: '审核队列回退（只读）', candidates: candidates.map((candidate, index) => ({
        cluster_id: `QUEUE-${index + 1}`, title: candidate.name,
        supporting_jd_count: candidate.evidence || 0, deduplicated_jd_count: candidate.evidence || 0,
        source_count: candidate.sourceCount || 1, threshold, threshold_met: (candidate.evidence || 0) > threshold,
        status: candidate.status || '观察中', workflow_stage: candidate.status || '待审核', candidate, evidence: [candidate],
      })), guardrails: ['候选聚类不会自动写入正式岗位池'],
    };
  }
};

export const importMonthlyJds = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${roleEvolutionBaseUrl.replace(/\/$/, '')}${roleEvolutionPath(
    '/jd-update/submissions/import?domain=company&processing_mode=manual',
    '/api/jd-update/submissions/import?domain=company&processing_mode=manual',
  )}`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    let detail = '';
    try { detail = (await response.json()).detail || ''; } catch { /* ignore malformed error bodies */ }
    throw new Error(detail || '月度 JD 导入失败');
  }
  return response.json();
};

export const deleteImportedMonth = async (month) => {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month || '')) {
    throw new Error('请选择需要清理的月份');
  }
  const query = new URLSearchParams({ domain: 'company', month });
  return roleEvolutionRequest(roleEvolutionPath(
    `/jd-update/discovery/imported-month?${query.toString()}`,
    `/api/discovery/imported-month?${query.toString()}`,
  ), { method: 'DELETE' });
};

export const runSyntheticNewRoleFixture = async () => {
  if (!roleEvolutionLiveEnabled) {
    return {
      synthetic_only: true,
      production_state_changed: false,
      fixture_jd_count: 12,
      route_statuses: ['potential_new_job'],
      batch: { month: '2026-08', unmapped_jd_count: 12, cluster_count: 1 },
      result_summary: {
        title: '边缘智能体编排工程师', supporting_jd_count: 12,
        threshold: 10, threshold_met: true, status: '待人工审核',
      },
    };
  }
  return roleEvolutionRequest(roleEvolutionPath(
    '/jd-update/discovery/fixtures/synthetic-new-role?domain=company',
    '/api/discovery/fixtures/synthetic-new-role?domain=company',
  ), { method: 'POST' });
};

export const getMarketChangeCandidates = async () => {
  if (!roleEvolutionLiveEnabled) return marketChangeCandidates;
  try {
    const rows = await roleEvolutionRequest(roleEvolutionPath(
      '/jd-update/cross-validation/candidates?domain=company',
      '/api/cross-validation/candidates?domain=company',
    ));
    return (Array.isArray(rows) ? rows : []).map((item) => ({
      id: `SKILL-${item.standard_job}-${item.skill}`,
      name: item.standard_job || '岗位能力变化',
      status: '待审核',
      confidence: Math.round(Number(item.confidence || item.score || 0) * 100),
      evidence: Number(item.evidence_count || 1),
      sourceCount: Number(item.evidence_count || 1),
      sources: [{ source: '岗位技能交叉验证', confidence: '后端候选能力池', excerpt: item.skill || '', collectedAt: item.updated_at || '' }],
      signals: [`发现候选能力：${item.skill || '未命名能力'}`],
      skills: [item.skill].filter(Boolean),
      domain: item.standard_job || '岗位能力变化',
      updatedAt: item.updated_at || '',
      version: '能力候选 v0.1',
      definition: { coreResponsibilities: [], requiredSkills: [item.skill].filter(Boolean), bonusSkills: [], scenarios: [], evidenceNote: '来自岗位能力交叉验证候选。' },
      raw: item,
    }));
  } catch {
    return marketChangeCandidates;
  }
};

export const reviewDiscoveryCandidate = async (id, decision, definition = {}) => {
  if (!roleEvolutionLiveEnabled) return { id, decision, status: decision === 'publish' ? 'published' : 'rejected' };
  if (decision !== 'publish') {
    const reviewId = definition.maintenanceId || id;
    return roleEvolutionRequest(roleEvolutionPath(
      `/jd-update/discovery/${encodeURIComponent(reviewId)}/reject?domain=company`,
      `/api/discovery/${encodeURIComponent(reviewId)}/reject?domain=company`,
    ), { method: 'POST' });
  }
  if (definition.maintenanceId) {
    return roleEvolutionRequest(roleEvolutionPath(
      `/jd-update/discovery/${encodeURIComponent(definition.maintenanceId)}/publish?domain=company`,
      `/api/discovery/${encodeURIComponent(definition.maintenanceId)}/publish?domain=company`,
    ), { method: 'POST' });
  }
  return roleEvolutionRequest(roleEvolutionPath(
    `/jd-update/discovery/${encodeURIComponent(id)}/submit-proposal?domain=company`,
    `/api/discovery/${encodeURIComponent(id)}/submit-proposal?domain=company`,
  ), {
    method: 'POST',
    body: JSON.stringify({
      standard_category: definition.category || '',
      standard_job_title: definition.name || '',
      match_keywords: definition.keywords || definition.name || '',
      core_responsibilities: definition.coreResponsibilities || [],
      required_skills: definition.requiredSkills || [],
      bonus_skills: definition.bonusSkills || [],
      application_scenarios: definition.scenarios || [],
      evidence_note: definition.evidenceNote || '',
      skills: definition.skills || [],
    }),
  });
};

export const reviewPendingJob = async (itemId, action, payload = {}) => {
  const path = action === 'confirm'
    ? `/jd-update/reviews/${encodeURIComponent(itemId)}/confirm-existing?domain=company`
    : `/jd-update/reviews/${encodeURIComponent(itemId)}/submit-new-job-proposal?domain=company`;
  const body = action === 'confirm'
    ? {
      standard_job_title: payload.standard_job_title || '',
      standard_category: payload.standard_category || '',
      skills: payload.skills || [],
    }
    : {
      standard_category: payload.standard_category || '',
      standard_job_title: payload.standard_job_title || '',
      match_keywords: payload.match_keywords || payload.standard_job_title || '',
      core_responsibilities: payload.core_responsibilities || [],
      required_skills: payload.required_skills || [],
      bonus_skills: payload.bonus_skills || [],
      application_scenarios: payload.application_scenarios || [],
      evidence_note: payload.evidence_note || '',
      source_review_ids: payload.source_review_ids || [],
      skills: payload.skills || [],
    };
  return roleEvolutionRequest(path, { method: 'POST', body: JSON.stringify(body) });
};

export const getCapabilityGraph = (year) => {
  const url = year ? `/api/v1/graph?year=${year}` : '/api/v1/graph';
  return fetch(url)
    .then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .catch((error) => {
      console.error('Graph API is unavailable:', error);
      throw error;
    });
};

export const getCapabilityRoleJobs = async ({ category, direction, role, limit = 8, offset = 0 }) => {
  const params = new URLSearchParams({
    category: category || '',
    direction: direction || '',
    role: role || '',
    limit: String(limit),
    offset: String(offset),
  });
  const response = await fetch(`/api/v1/graph/role-jobs?${params.toString()}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
};

export const getRoleEvolution = () => mockOnly(evolutionData);

const fitLabels = {
  excellent: 'excellent match',
  good: 'good match',
  fair: 'partial match',
  poor: 'weak match',
};

const toPercent = (score) => Math.round(Math.max(0, Math.min(1, Number(score) || 0)) * 100);
const clampScore = (score) => Math.max(0, Math.min(1, Number(score) || 0));

const toDisplayText = (value) => {
  if (value == null) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map(toDisplayText).filter(Boolean).join('、');
  if (typeof value === 'object') {
    const matched = Array.isArray(value.matched_skills) ? value.matched_skills.map(toDisplayText).filter(Boolean).join('、') : '';
    const missing = Array.isArray(value.missing_skills) ? value.missing_skills.map(toDisplayText).filter(Boolean).join('、') : '';
    const reason = value.reason ? toDisplayText(value.reason) : '';
    return [
      matched && `匹配技能：${matched}`,
      missing && `待补充技能：${missing}`,
      reason,
    ].filter(Boolean).join('；') || JSON.stringify(value);
  }
  return String(value);
};

const normalizeTextList = (values = []) => (Array.isArray(values) ? values : [values])
  .map(toDisplayText)
  .map((value) => value.trim())
  .filter(Boolean);

const readRuntimePreference = (key, fallback) => {
  try {
    const value = localStorage.getItem(key);
    return value || fallback;
  } catch {
    return fallback;
  }
};

const extractSkills = (candidateProfile) => {
  const candidate = candidateProfile.candidate || {};
  return candidateProfile.extracted_skills?.length
    ? normalizeTextList(candidateProfile.extracted_skills)
    : normalizeTextList((candidate.skills || []).map((skill) => skill.name || skill));
};

const makeGapItems = (skills, sourceLabel) => normalizeTextList(skills).slice(0, 3).map((skill, gapIndex) => ({
  skill,
  priority: gapIndex < 2 ? 'high' : 'medium',
  current: 0,
  target: 100,
  reason: `${sourceLabel} requires ${skill}, but the current resume evidence is insufficient.`,
}));

const normalizeLiveDiagnosis = (candidateProfile, recommendations, jobs, pipelineWarning = null) => {
  const candidate = candidateProfile.candidate || {};
  const skills = extractSkills(candidateProfile);
  const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false });

  const matches = recommendations.slice(0, 3).map((recommendation, index) => {
    const job = jobs[index] || {};
    const matchingSkills = normalizeTextList(recommendation.matching_skills);
    const missingSkills = normalizeTextList(recommendation.missing_skills);
    const score = toPercent(recommendation.match_score);
    const requiredSkillCount = Math.max(1, (job.required_skills || []).length);
    const evidenceCoverage = Math.round((matchingSkills.length / requiredSkillCount) * 100);

    return {
      id: recommendation.job_id,
      role: job.title || `Job ${index + 1}`,
      family: job.job_family || job.company_name || 'job family pending',
      company: job.company_name || '',
      version: 'current JD',
      score,
      reason: matchingSkills.length
        ? `${fitLabels[recommendation.overall_fit] || 'matched'} with evidence in ${matchingSkills.slice(0, 4).join(', ')}.`
        : `${fitLabels[recommendation.overall_fit] || 'matched'} based mainly on resume and job semantic relevance.`,
      gaps: makeGapItems(missingSkills, 'The job'),
      matchingSkills,
      evidenceCoverage: Math.max(0, Math.min(100, evidenceCoverage)),
      job,
    };
  });

  return {
    source: 'live',
    generatedAt,
    profile: {
      name: candidate.name || 'unknown candidate',
      target: matches[0]?.role || 'target role pending',
      confidence: null,
      skills,
      experienceCount: candidate.experience?.length || 0,
      yearsExperience: Number(candidate.years_experience) || 0,
      experience: candidateProfile.experience_summary
        || `Parsed ${candidate.experience?.length || 0} work or project experience records.`,
    },
    matches,
    gaps: matches[0]?.gaps || [],
    pipeline: {
      mode: pipelineWarning ? 'legacy-fallback' : 'legacy',
      warning: pipelineWarning,
      capabilities: ['resume parsing', 'legacy job recommendation'],
    },
  };
};

const normalizeCanonicalDiagnosis = (candidateProfile, searchResult) => {
  const candidate = candidateProfile.candidate || {};
  const jobs = searchResult?.jobs || [];
  const selectedRole = searchResult?.explanations?.selected_canonical_role || '';
  const roleCandidates = searchResult?.explanations?.top_role_candidates || [];
  const selectedRoleJdCandidates = searchResult?.explanations?.selected_role_jd_candidates || [];
  const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false });
  // Prefer the backend's Top-3 *distinct third-level roles*. The first role
  // remains the closed-set winner; the other two are alternatives, each with
  // a representative JD only as explanation evidence.
  const displayCandidates = roleCandidates.length
    ? roleCandidates.map((candidateRole) => ({
      job: candidateRole.representative_job,
      roleScore: candidateRole.role_score,
    })).filter((candidate) => candidate.job)
    : jobs.slice(0, 3).map((job) => ({ job, roleScore: null }));
  const matches = displayCandidates.map(({ job, roleScore }, index) => {
    const metadata = job.search_metadata || {};
    const explanation = metadata.match_explanation || {};
    const details = explanation.components?.['Skill Match']?.details || {};
    const matchingSkills = normalizeTextList(details.matched_skills);
    const missingSkills = normalizeTextList(details.missing_skills);
    const role = metadata.canonical_role || job.job_family || job.title || `Job ${index + 1}`;
    return {
      id: job.id,
      role,
      family: metadata.canonical_direction || 'v2 功能型三级岗位',
      company: job.company_name || '',
      version: 'canonical role pool v2',
      roleScore: toPercent(roleScore ?? metadata.role_match_score ?? job.rerank_score),
      score: toPercent(job.rerank_score),
      jdFitScore: toPercent(metadata.jd_fit_score ?? job.rerank_score),
      roleConfidence: toPercent(roleScore ?? metadata.role_confidence ?? metadata.role_match_score),
      reason: matchingSkills.length
        ? `基于岗位内技能证据匹配：${matchingSkills.slice(0, 5).join('、')}`
        : '已在匹配到的三级标准岗位内完成 JD 排序。',
      gaps: makeGapItems(missingSkills, '岗位'),
      matchingSkills,
      evidenceCoverage: toPercent(explanation.components?.['Job Description Match']?.score),
      jdQuality: metadata.jd_quality || null,
      requiredSkillGroupCount: metadata.required_skill_group_count ?? null,
      jdCandidates: index === 0 ? selectedRoleJdCandidates : [],
      jobTitle: job.title || '',
      canonicalRoleId: metadata.canonical_role_id || null,
      canonicalRole: metadata.canonical_role || role,
      canonicalDirection: metadata.canonical_direction || null,
      roleMappingStatus: 'mapped',
      job,
    };
  });

  return {
    source: 'live',
    generatedAt,
    profile: {
      name: candidate.name || 'unknown candidate',
      target: selectedRole || matches[0]?.role || 'target role pending',
      confidence: null,
      skills: extractSkills(candidateProfile),
      experienceCount: candidate.experience?.length || 0,
      yearsExperience: Number(candidate.years_experience) || 0,
      experience: candidateProfile.experience_summary
        || `Parsed ${candidate.experience?.length || 0} work or project experience records.`,
    },
    matches,
    gaps: matches[0]?.gaps || [],
    pipeline: {
      mode: 'canonical-two-stage',
      warning: null,
      capabilities: ['enhanced resume parsing', 'canonical role selection', 'in-role JD ranking'],
    },
  };
};

const buildCandidateQuery = (candidateProfile) => {
  const candidate = candidateProfile.candidate || {};
  const skills = extractSkills(candidateProfile);
  const experience = (candidate.experience || [])
    .flatMap((item) => [item.position, item.description])
    .filter(Boolean);

  return [candidate.target_job_family, candidate.summary, ...skills, ...experience, candidateProfile.experience_summary]
    .filter(Boolean)
    .join(' ')
    .trim();
};

const normalizeBm25Scores = (hits) => {
  const maxScore = Math.max(...hits.map((hit) => Number(hit.score) || 0), 0);
  return new Map(hits.map((hit) => [hit.job_id, maxScore ? (Number(hit.score) || 0) / maxScore : 0]));
};

const normalizeFullDiagnosis = (candidateProfile, hits, gapByJobId, fusionResults) => {
  const candidate = candidateProfile.candidate || {};
  const hitByJobId = new Map(hits.map((hit) => [hit.job_id, hit]));
  const skills = extractSkills(candidateProfile);
  const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false });

  const matches = fusionResults.slice(0, 3).map((result, index) => {
    const hit = hitByJobId.get(result.job_id) || {};
    const gap = gapByJobId.get(result.job_id) || {};
    const matchingSkills = normalizeTextList(gap.matched_skills);
    const missingSkills = normalizeTextList(result.missing_skills || gap.missing_skills);

    return {
      id: result.job_id,
      role: result.canonical_role || hit.standard_job || hit.title || `Job ${index + 1}`,
      family: result.canonical_direction || hit.job_family || hit.standard_category || 'job family pending',
      company: hit.company || '',
      version: 'current graph version',
      score: toPercent(result.final_score),
      reason: toDisplayText(result.explanation) || `Ranked by BM25, semantic rerank, knowledge graph gap analysis, and fusion scoring. Current rank: ${result.rank || index + 1}.`,
      gaps: makeGapItems(missingSkills, 'The knowledge graph'),
      matchingSkills,
      evidenceCoverage: toPercent(gap.skill_coverage),
      evidencePaths: normalizeTextList(result.evidence_paths || gap.evidence_paths),
      scoreBreakdown: result.score_breakdown || null,
      canonicalRoleId: result.canonical_role_id || null,
      canonicalRole: result.canonical_role || null,
      canonicalDirection: result.canonical_direction || null,
      roleMappingStatus: result.role_mapping_status || null,
      job: {
        id: result.job_id,
        title: hit.title,
        standard_job: hit.standard_job,
        company_name: hit.company,
        job_family: hit.job_family,
        required_skills: normalizeTextList(gap.job_required_skills || hit.skills),
        description: hit.description,
        requirements: hit.requirements,
        responsibilities: hit.responsibilities,
        location: hit.location,
      },
    };
  });

  return {
    source: 'live',
    generatedAt,
    profile: {
      name: candidate.name || 'unknown candidate',
      target: matches[0]?.role || 'target role pending',
      confidence: null,
      skills,
      experience: candidateProfile.experience_summary
        || `Parsed ${candidate.experience?.length || 0} work or project experience records.`,
    },
    matches,
    gaps: matches[0]?.gaps || [],
    pipeline: {
      mode: 'full',
      warning: null,
      capabilities: ['BM25 retrieval', 'semantic rerank', 'knowledge graph gap analysis', 'fusion ranking'],
    },
  };
};

const ROLE_AWARE_CANDIDATE_POOL_SIZE = 100;

const runFullDiagnosisPipeline = async (candidateProfile) => {
  const candidateId = candidateProfile.candidate?.id;
  const queryText = buildCandidateQuery(candidateProfile);
  if (!candidateId || !queryText) throw new Error('Resume profile lacks candidate id or searchable text.');

  const bm25Result = await searchBm25(queryText, { size: ROLE_AWARE_CANDIDATE_POOL_SIZE });
  const hits = (bm25Result.hits || []).filter((hit) => hit.job_id);
  if (!hits.length) throw new Error('BM25 index returned no candidate jobs.');

  const semanticResult = await rerankSemantic({
    queryId: candidateId,
    queryText,
    candidates: hits.map((hit) => ({
      job_id: hit.job_id,
      title: hit.standard_job || hit.title || '',
      description: [hit.description, hit.requirements, hit.responsibilities].filter(Boolean).join(' '),
      required_skills: hit.skills || [],
    })),
  });
  const semanticByJobId = new Map(
    (semanticResult.candidates || []).map((candidate) => [candidate.job_id, Number(candidate.semantic_score) || 0])
  );

  const gapResults = await Promise.allSettled(
    hits.map((hit) => analyzeKnowledgeGraphGap(candidateId, hit.job_id))
  );
  const gapByJobId = new Map();
  gapResults.forEach((result) => {
    if (result.status === 'fulfilled' && result.value.job_required_skills?.length) {
      gapByJobId.set(result.value.job_id, result.value);
    }
  });
  if (!gapByJobId.size) {
    throw new Error('BM25 job ids are not aligned with knowledge graph job ids, so gap analysis cannot be completed.');
  }

  const bm25ByJobId = normalizeBm25Scores(hits);
  const fusionInputs = hits.filter((hit) => gapByJobId.has(hit.job_id)).map((hit) => {
    const gap = gapByJobId.get(hit.job_id);
    return {
      query_id: candidateId,
      job_id: hit.job_id,
      bm25_score: bm25ByJobId.get(hit.job_id) || 0,
      semantic_score: clampScore(semanticByJobId.get(hit.job_id)),
      skill_coverage: clampScore(gap.skill_coverage),
      job_family_match: clampScore(gap.job_family_match),
      graph_relatedness: clampScore(gap.graph_relatedness),
      missing_skills: normalizeTextList(gap.missing_skills),
      evidence_paths: normalizeTextList(gap.evidence_paths),
      _meta: {
        title: hit.title,
        standard_job: hit.standard_job,
        job_family: hit.job_family,
        required_skills: hit.skills || [],
        company: hit.company,
        location: hit.location,
        source_type: hit.source_type,
      },
    };
  });
  const fusionResult = await rankJobs(candidateId, fusionInputs);
  if (!fusionResult.results?.length) throw new Error('Fusion ranking returned no results.');

  const hitByJobId = new Map(hits.map((hit) => [hit.job_id, hit]));
  let rankedResults = fusionResult.results;
  try {
    const roleAwareResult = await rankRoleAware({
      queryId: candidateId,
      jobs: fusionResult.results.map((result) => {
        const hit = hitByJobId.get(result.job_id) || {};
        return {
          ...result,
          title: hit.title,
          standard_job: hit.standard_job,
          job_family: hit.job_family,
          required_skills: hit.skills || [],
          meta: {
            title: hit.title,
            standard_job: hit.standard_job,
            job_family: hit.job_family,
            required_skills: hit.skills || [],
          },
        };
      }),
      topK: 3,
      roleTopK: 1,
      candidateRoleId: candidateProfile.candidate?.canonical_role_id || null,
    });
    if (roleAwareResult?.results?.length) rankedResults = roleAwareResult.results;
  } catch (roleAwareError) {
    // The role gate is additive; preserve the existing fused result if unavailable.
    console.warn('Role-aware adapter unavailable, keeping fusion ranking:', roleAwareError);
  }

  return normalizeFullDiagnosis(candidateProfile, hits, gapByJobId, rankedResults);
};

const diagnoseUploadedResume = async (resumeFile, parserModeOverride, pipelineModeOverride) => {
  const parserMode = parserModeOverride || readRuntimePreference('resumeParserMode', 'auto');
  const pipelineMode = pipelineModeOverride || readRuntimePreference('matchingPipelineMode', 'lightweight');
  const candidateProfile = await uploadResume(resumeFile, parserMode);
  // The dependency-light local runtime returns canonical v2 results directly.
  // Use that result before attempting the older multi-service diagnosis chain.
  try {
    const canonicalResult = await searchJobsWithResume(
      {
        query: buildCandidateQuery(candidateProfile) || 'software engineer',
        page: 1,
        page_size: 10,
        limit: 10,
        pipeline_mode: pipelineMode,
      },
      resumeFile,
      parserMode,
    );
    if (canonicalResult?.explanations?.matching_pipeline === 'canonical_two_stage_v2') {
      return normalizeCanonicalDiagnosis(candidateProfile, canonicalResult);
    }
  } catch (canonicalError) {
    console.warn('Canonical resume matching unavailable, trying full diagnosis pipeline:', canonicalError);
  }
  try {
    return await runFullDiagnosisPipeline(candidateProfile);
  } catch (pipelineError) {
    const recommendations = await getJobRecommendations(candidateProfile.candidate);
    if (!recommendations.length) {
      throw new Error(`Resume parsing succeeded, but the full matching pipeline is unavailable and legacy recommendation returned no result: ${pipelineError.message}`);
    }

    const jobResults = await Promise.allSettled(
      recommendations.slice(0, 3).map((match) => getJobById(match.job_id))
    );
    const jobs = jobResults.map((result) => result.status === 'fulfilled' ? result.value : null);
    return normalizeLiveDiagnosis(candidateProfile, recommendations, jobs, pipelineError.message);
  }
};

// Only resume diagnosis has a complete backend contract. Other workbench modules
// intentionally remain on mock data until their talent-intelligence APIs exist.
export const diagnoseCandidate = ({ resumeFile, parserMode, pipelineMode } = {}) => {
  if (!resumeFile || process.env.REACT_APP_USE_RESUME_MOCK === 'true') return Promise.resolve(diagnosisData);
  return diagnoseUploadedResume(resumeFile, parserMode, pipelineMode);
};
export const getDataGovernance = () => mockOnly(governanceData);
export const getEvaluationReport = () => mockOnly(evaluationData);
export const getRoleCatalog = () => mockOnly(roleCatalogData);
export const getLearningPlan = async () => {
  let target = null;
  try { target = JSON.parse(localStorage.getItem('careerTarget')); } catch { target = null; }
  if (!target?.role) return learningPlanData;

  try {
    const raw = await generateLearningPlan({
      targetRole: target.role,
      missingSkills: (target.gaps || []).map((gap) => (typeof gap === 'string' ? gap : gap?.skill)).filter(Boolean),
      targetVersion: target.version,
      matchScore: target.score != null ? Number(target.score) / 100 : null,
    });

    return {
      profile: raw.profile || '求职者',
      targetRole: raw.target_role || target.role,
      targetVersion: raw.target_version || target.version,
      matchScore: raw.match_score != null ? Math.round(raw.match_score * 100) : target.score,
      progress: raw.progress || 0,
      currentStage: raw.current_stage || '阶段 1',
      updatedAt: raw.updated_at || new Date().toLocaleString('zh-CN', { hour12: false }),
      gapCount: raw.gap_count || (raw.stages || []).length,
      stages: (raw.stages || []).map((stage) => ({
        id: stage.id,
        phase: stage.phase || stage.learning_stage || '阶段 1',
        title: stage.title,
        duration: stage.duration || '1 周',
        status: stage.status,
        goal: stage.goal || stage.suggestion,
        tasks: stage.tasks || [],
        outcome: stage.outcome,
        skill: stage.skill,
      })),
    };
  } catch (error) {
    console.warn('Learning plan API unavailable, falling back to mock:', error);
    return learningPlanData;
  }
};

const roleEvolutionApiUrl = process.env.REACT_APP_ROLE_EVOLUTION_API_URL;
const roleEvolutionBaseUrl = roleEvolutionApiUrl || process.env.REACT_APP_API_URL || '/api/v1';
const roleEvolutionUsesStandaloneApi = Boolean(roleEvolutionApiUrl);
const roleEvolutionLiveEnabled = process.env.NODE_ENV !== 'test'
  || Boolean(roleEvolutionApiUrl || process.env.REACT_APP_API_URL);

const roleEvolutionPath = (integratedPath, standalonePath) => (
  roleEvolutionUsesStandaloneApi ? standalonePath : integratedPath
);

const roleEvolutionRequest = async (path, options = {}) => {
  const response = await fetch(`${roleEvolutionBaseUrl.replace(/\/$/, '')}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`岗位演化服务请求失败（${response.status}）`);
  return response.json();
};

const skillName = (skill) => {
  if (typeof skill === 'string') return skill;
  return skill?.skill || skill?.normalized_skill || skill?.name || skill?.raw_skill || '';
};

const asList = (value) => Array.isArray(value) ? value : [];

const normalizeProcessResult = (item, input = {}) => {
  const result = item?.result || item || {};
  const route = result.route || {};
  const role = route.best_job?.name || result.job_title || input.job_title || '未归类岗位';
  const skills = (result.skills || []).map(skillName).filter(Boolean);
  const crossValidation = Array.isArray(result.cross_validation) ? result.cross_validation : [];
  const candidateSkillCount = crossValidation.filter((item) => ['candidate', 'confirmed_dynamic', 'confirmed_cross_role'].includes(item?.status)).length;
  const update = result.update || {};
  const effect = result.live_update_effect || {};
  const changes = effect.changes || {};
  const updatedAt = item?.updated_at || item?.created_at || new Date().toISOString().slice(0, 10);
  return {
    effectId: effect.effect_id || item?.item_id || item?.effect_id || item?.preview_id || 'EV-local',
    id: effect.effect_id || item?.item_id || item?.effect_id || item?.preview_id || 'EV-local',
    role: effect.standard_job || role,
    version: effect.month || update.month || input.month || '当前版本',
    status: item?.status === 'auto_merged' ? '已发布' : '待审核',
    summary: route.reason || (skills.length ? `识别到 ${skills.length} 项岗位能力要求。` : '已完成岗位归类与技能分析。'),
    added: changes.added?.map(skillName).filter(Boolean) || skills,
    removed: changes.removed?.map(skillName).filter(Boolean) || [],
    modified: [...(changes.increased || []), ...(changes.decreased || [])].map(skillName).filter(Boolean),
    evidence: skills.length,
    crossValidation,
    candidateSkillCount,
    updatedAt,
    input,
    raw: item,
  };
};

const normalizeLiveEffect = (effect) => {
  const changes = effect?.changes || {};
  const added = asList(changes.added).map(skillName).filter(Boolean);
  const increased = asList(changes.increased).map(skillName).filter(Boolean);
  const decreased = asList(changes.decreased).map(skillName).filter(Boolean);
  const removed = asList(changes.removed).map(skillName).filter(Boolean);
  const signalSkills = asList(effect?.signal_skills).map(skillName).filter(Boolean);
  const summary = effect?.summary || {};
  const summaryParts = [
    added.length && `新增 ${added.length} 项技能`,
    increased.length && `${increased.length} 项技能需求上升`,
    decreased.length && `${decreased.length} 项技能需求下降`,
    removed.length && `移除 ${removed.length} 项技能`,
  ].filter(Boolean);
  return {
    effectId: effect?.effect_id || 'EV-confirmed',
    id: effect?.effect_id || 'EV-confirmed',
    role: effect?.standard_job || '已确认岗位更新',
    version: effect?.month || '当前版本',
    status: '已生效',
    summary: summaryParts.length
      ? `已基于确认 JD 更新岗位画像：${summaryParts.join('；')}。`
      : '该 JD 已归入岗位画像，但未改变已记录的技能频率。',
    added,
    removed,
    modified: [...increased.map((skill) => `${skill} ↑`), ...decreased.map((skill) => `${skill} ↓`)],
    evidence: signalSkills.length || Number(summary.signal_skills || 0),
    candidateSkillCount: 0,
    updatedAt: effect?.created_at || effect?.month || '',
    input: { month: effect?.month || '', job_title: effect?.standard_job || '' },
    raw: effect,
  };
};

const normalizeAnalytics = (raw, fallback) => {
  const trendSeries = raw?.trend?.series || [];
  const trend = trendSeries.length
    ? (raw.trend.months || []).map((month, index) => ({
      month,
      frequency: Math.max(...trendSeries.map((series) => Number(series.points?.[index]?.frequency || 0)), 0),
    }))
    : fallback.trend;
  const lifecycleRows = raw?.lifecycle?.rows || [];
  const lifecycle = lifecycleRows.length
    ? lifecycleRows
      .filter((row) => Number(row.current_monthly_skill_frequency || row.monthly_skill_frequency || 0) > 0 || Number(row.recent_3m_skill_count || 0) > 0)
      .sort((a, b) => Number(b.current_monthly_skill_frequency || b.monthly_skill_frequency || 0) - Number(a.current_monthly_skill_frequency || a.monthly_skill_frequency || 0))
      .slice(0, 12).map((row) => ({
        skill: skillName(row),
        status: row.lifecycle_status || row.snapshot_skill_status || '观察中',
        frequency: Number(row.current_monthly_skill_frequency || row.monthly_skill_frequency || 0),
        change: row.mom_frequency_change == null ? '' : `${Number(row.mom_frequency_change) >= 0 ? '+' : ''}${Number(row.mom_frequency_change).toFixed(2)}`,
      }))
    : fallback.lifecycle;
  const migrationRows = raw?.migration?.spread || [];
  const migration = migrationRows.length
    ? migrationRows.slice(0, 12).map((row) => ({
      from: row.from_skill || row.source_skill || row.standard_job || '技能来源',
      to: row.to_skill || row.target_skill || skillName(row),
      weight: Number(row.migration_weight || row.weight || row.monthly_skill_frequency || 0),
    }))
    : fallback.migration;
  return { ...fallback, trend, lifecycle, migration };
};

const normalizeRoleEvolution = (profileCompare, role) => {
  const changes = profileCompare?.changes || {};
  const added = asList(changes.added).map(skillName).filter(Boolean);
  const removed = asList(changes.removed).map(skillName).filter(Boolean);
  const increased = asList(changes.increased).map(skillName).filter(Boolean);
  const decreased = asList(changes.decreased).map(skillName).filter(Boolean);
  const fromMonth = profileCompare?.from_month || '起始月份';
  const toMonth = profileCompare?.to_month || '当前月份';
  const latestProfile = asList(profileCompare?.to_profile);
  const summary = profileCompare?.summary || {};
  return {
    id: `PROFILE-${role}-${toMonth}`,
    role: profileCompare?.standard_job || role,
    version: `${fromMonth} 至 ${toMonth}`,
    status: '时序画像对比',
    summary: `基于 ${fromMonth} 至 ${toMonth} 的版本化 JD 画像：新增 ${Number(summary.added || added.length)} 项能力；需求上升 ${Number(summary.increased || increased.length)} 项；需求下降 ${Number(summary.decreased || decreased.length)} 项。`,
    added,
    removed,
    modified: [...increased.map((skill) => `${skill} ↑`), ...decreased.map((skill) => `${skill} ↓`)],
    evidence: latestProfile.length,
    candidateSkillCount: 0,
    updatedAt: latestProfile[0]?.updated_at || toMonth,
    input: { month: toMonth, job_title: profileCompare?.standard_job || role },
    raw: { signal_skills: latestProfile.map(skillName).filter(Boolean) },
  };
};

const profileVersions = (profileCompare) => {
  const from = asList(profileCompare?.from_profile);
  const to = asList(profileCompare?.to_profile);
  const build = (month, rows, summary) => ({
    version: month || '未提供月份',
    date: rows[0]?.updated_at || month || '',
    summary,
  });
  if (!profileCompare?.from_month && !profileCompare?.to_month) return [];
  return [
    build(profileCompare.from_month, from, `起始画像：${from.length} 项可用技能证据。`),
    build(profileCompare.to_month, to, `最新画像：${to.length} 项可用技能证据。`),
  ];
};

const roleEvolutionFallback = () => ({
  jobs: roleCatalogData,
  pending: [...discoveryCandidates, ...marketChangeCandidates],
  latest: {
    id: 'EV-20260725-01',
    role: evolutionData.role,
    version: evolutionData.versions[0].version,
    status: '待发布',
    summary: evolutionData.versions[0].summary,
    added: evolutionData.versions[0].added,
    removed: evolutionData.versions[0].removed,
    modified: evolutionData.versions[0].modified,
    evidence: evolutionData.versions[0].evidence,
    updatedAt: evolutionData.versions[0].date,
  },
  analytics: {
    role: evolutionData.role,
    versions: evolutionData.versions,
    trend: [
      { month: '2025-12', frequency: 0.42 },
      { month: '2026-02', frequency: 0.51 },
      { month: '2026-04', frequency: 0.64 },
      { month: '2026-07', frequency: 0.78 },
    ],
    lifecycle: [
      { skill: 'Agent 工作流', status: '快速上升', frequency: 0.78, change: '+18%' },
      { skill: '模型评测', status: '新兴', frequency: 0.61, change: '+21%' },
      { skill: '传统 NLP 管线', status: '衰退', frequency: 0.18, change: '-14%' },
    ],
    migration: [
      { from: 'RAG 基础使用', to: '检索质量优化', weight: 0.72 },
      { from: '传统 NLP 管线', to: 'Agent 工作流', weight: 0.48 },
    ],
  },
  optimization: roleCatalogData[0],
});

export const getRoleEvolutionWorkspace = async () => {
  const fallback = roleEvolutionFallback();
  if (!roleEvolutionLiveEnabled) return fallback;
  try {
    const jobsResponse = await roleEvolutionRequest(roleEvolutionPath('/jd-update/analytics/jobs?domain=company', '/api/analytics/jobs?domain=company'));
    const jobNames = Array.isArray(jobsResponse) ? jobsResponse : [];
    const analyticsRole = jobNames.includes(fallback.analytics.role) ? fallback.analytics.role : (jobNames[0] || fallback.analytics.role);
    const standardJobQuery = `&standard_job=${encodeURIComponent(analyticsRole)}`;
    const [overview, reviewItems, optimization, trend, lifecycle, migration, latestEffect] = await Promise.all([
      roleEvolutionRequest(roleEvolutionPath('/jd-update/analytics/overview?domain=company', '/api/analytics/overview?domain=company')),
      roleEvolutionRequest(roleEvolutionPath('/jd-update/reviews?domain=company', '/api/review/items?domain=company')),
      roleEvolutionRequest(roleEvolutionPath(
        `/jd-update/optimization/profile?domain=company&standard_job=${encodeURIComponent(analyticsRole)}`,
        `/api/optimization/profile?domain=company&standard_job=${encodeURIComponent(analyticsRole)}`,
      )),
      roleEvolutionRequest(roleEvolutionPath(`/jd-update/analytics/job-trend?domain=company${standardJobQuery}`, `/api/analytics/job-trend?domain=company${standardJobQuery}`)),
      roleEvolutionRequest(roleEvolutionPath(`/jd-update/analytics/lifecycle?domain=company${standardJobQuery}`, `/api/analytics/lifecycle?domain=company${standardJobQuery}`)),
      roleEvolutionRequest(roleEvolutionPath('/jd-update/analytics/skill-migration?domain=company', '/api/analytics/skill-migration?domain=company')),
      roleEvolutionRequest(roleEvolutionPath('/jd-update/live-evolution/latest?domain=company', '/api/live-evolution/latest?domain=company')),
    ]);
    const profileRows = Array.isArray(optimization?.skills) ? optimization.skills : [];
    const latestReview = Array.isArray(reviewItems) ? reviewItems[0] : null;
    const latest = latestEffect ? normalizeLiveEffect(latestEffect) : (latestReview ? normalizeProcessResult(latestReview) : fallback.latest);
    return {
      ...fallback,
      jobs: jobNames.length ? jobNames.map((name) => ({ name, summary: '来自岗位技能演化数据源的岗位画像。', requiredSkills: [] })) : fallback.jobs,
      pending: Array.isArray(reviewItems) ? reviewItems : fallback.pending,
      latest,
      analytics: {
        ...normalizeAnalytics(
          { trend, lifecycle, migration },
          { ...fallback.analytics, role: analyticsRole, ...(overview || {}) },
        ),
        // Version windows must come from the selected role's profile comparison.
        // Do not carry static fallback versions into a live workspace.
        versions: [],
      },
      optimization: profileRows.length ? {
        ...fallback.optimization,
        name: optimization.standard_job || fallback.optimization.name,
        summary: `来源月份：${optimization.summary?.source_month || '当前运行数据'}`,
        requiredSkills: profileRows.map((skill) => ({ name: skillName(skill) })).filter((skill) => skill.name),
      } : fallback.optimization,
    };
  } catch {
    return fallback;
  }
};

export const submitRoleJd = async (payload) => {
  if (!roleEvolutionLiveEnabled) return { effectId: 'EV-20260725-01', status: '待审核', ...roleEvolutionFallback().latest, input: payload };
  try {
    if (roleEvolutionUsesStandaloneApi) {
      const result = await roleEvolutionRequest('/api/jobs/submit-one-dry-run?domain=company', { method: 'POST', body: JSON.stringify(payload) });
      return normalizeProcessResult(result, payload);
    }
    const preview = await roleEvolutionRequest('/jd-update/submissions/preview', { method: 'POST', body: JSON.stringify({ ...payload, domain: 'company' }) });
    const result = await roleEvolutionRequest('/jd-update/submissions', {
      method: 'POST',
      body: JSON.stringify({ domain: 'company', preview_id: preview.preview_id, processing_mode: payload.processing_mode || 'manual' }),
    });
    return normalizeProcessResult(result, payload);
  } catch {
    return { effectId: 'EV-20260725-01', status: '待审核', ...roleEvolutionFallback().latest, input: payload };
  }
};

export const getLiveEvolution = async (effectId) => {
  if (!roleEvolutionLiveEnabled) return roleEvolutionFallback().latest;
  try {
    const result = await roleEvolutionRequest(roleEvolutionPath(
      `/jd-update/live-evolution/${encodeURIComponent(effectId)}?domain=company`,
      `/api/live-evolution/${encodeURIComponent(effectId)}?domain=company`,
    ));
    return normalizeProcessResult(result);
  } catch {
    return roleEvolutionFallback().latest;
  }
};

export const getRoleAnalytics = async (params = {}) => {
  if (!roleEvolutionLiveEnabled) return roleEvolutionFallback().analytics;
  try {
    const query = new URLSearchParams({ domain: 'company', ...params }).toString();
    const endpoint = (integratedPath, standalonePath) => roleEvolutionPath(`${integratedPath}?${query}`, `${standalonePath}?${query}`);
    const [overview, trend, lifecycle, migration, profileCompare] = await Promise.all([
      roleEvolutionRequest(endpoint('/jd-update/analytics/overview', '/api/analytics/overview')),
      roleEvolutionRequest(endpoint('/jd-update/analytics/job-trend', '/api/analytics/job-trend')),
      roleEvolutionRequest(endpoint('/jd-update/analytics/lifecycle', '/api/analytics/lifecycle')),
      roleEvolutionRequest(endpoint('/jd-update/analytics/skill-migration', '/api/analytics/skill-migration')),
      roleEvolutionRequest(endpoint('/jd-update/analytics/profile-compare', '/api/analytics/profile-compare')),
    ]);
    const fallback = roleEvolutionFallback().analytics;
    const role = params.standard_job || profileCompare?.standard_job || fallback.role;
    return {
      overview,
      trend,
      lifecycle,
      migration,
      profileCompare,
      analytics: {
        ...normalizeAnalytics(
        { trend, lifecycle, migration },
        { ...fallback, role, ...(overview || {}) },
        ),
        versions: profileVersions(profileCompare),
      },
      roleEvolution: normalizeRoleEvolution(profileCompare, role),
    };
  } catch {
    return roleEvolutionFallback().analytics;
  }
};

export const saveRoleOptimization = async (payload) => {
  if (!roleEvolutionLiveEnabled) return { status: '已保存', version: 'v1.3', ...payload };
  try {
    return await roleEvolutionRequest(roleEvolutionPath('/jd-update/optimization/overrides?domain=company', '/api/optimization/overrides?domain=company'), { method: 'POST', body: JSON.stringify(payload) });
  } catch {
    return { status: '已保存', version: 'v1.3', ...payload };
  }
};

export const getCrossValidationCandidates = async (status = '') => {
  if (!roleEvolutionLiveEnabled) return [];
  const query = status ? `&status=${encodeURIComponent(status)}` : '';
  return roleEvolutionRequest(roleEvolutionPath(
    `/jd-update/cross-validation/candidates?domain=company${query}`,
    `/api/cross-validation/candidates?domain=company${query}`,
  ));
};

export const reviewCrossValidationCandidate = async ({ standard_job, skill, action }) => {
  return roleEvolutionRequest(roleEvolutionPath(
    '/jd-update/cross-validation/candidates/review?domain=company',
    '/api/cross-validation/candidates/review?domain=company',
  ), { method: 'POST', body: JSON.stringify({ standard_job, skill, action }) });
};
export const getLiveMarketTrend = (skill) => getMarketTrends(skill);
export const getMarketRuntimeStatus = async () => {
  const [runtimeResult, datasetResult] = await Promise.allSettled([
    getMarketRuntime(),
    getTalentMarketStats(),
  ]);
  const runtime = runtimeResult.status === 'fulfilled'
    ? runtimeResult.value
    : { available: false, ingestion: null, bm25: null };
  return {
    ...runtime,
    dataset: datasetResult.status === 'fulfilled' ? datasetResult.value : null,
    available: runtime.available || datasetResult.status === 'fulfilled',
  };
};
export const importMarketCsv = (file) => ingestMarketCsv(file);

export const getJdQualitySample = async ({ limit = 30, useLlm = false, llmLimit = 5 } = {}) => {
  const query = new URLSearchParams({
    limit: String(limit),
    use_llm: String(useLlm),
    llm_limit: String(llmLimit),
  });
  const response = await fetch(`/api/v1/jd-quality/sample?${query.toString()}`);
  if (!response.ok) throw new Error(`JD quality audit failed: HTTP ${response.status}`);
  return response.json();
};

export const auditJdQualityBatch = async ({ jobs = [], useLlm = false, llmLimit = 5 } = {}) => {
  const response = await fetch('/api/v1/jd-quality/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jobs, use_llm: useLlm, llm_limit: llmLimit }),
  });
  if (!response.ok) throw new Error(`JD quality batch audit failed: HTTP ${response.status}`);
  return response.json();
};

export const getRecruitmentJobs = async (options = {}) => {
  try {
    return await getTalentJobs(options);
  } catch (error) {
    return {
      items: recruitmentJobsData.map((job) => ({ ...job, dataSource: 'mock-fallback' })),
      total: recruitmentJobsData.length,
      source: 'mock-fallback',
      warning: error.message,
    };
  }
};
export const saveRecruitmentJob = async (job) => {
  try {
    return await putTalentJob(job);
  } catch (error) {
    if (job.dataSource !== 'mock-fallback') throw error;
    return { ...job, dataSource: 'mock-fallback', warning: error.message };
  }
};
export const getJobCandidates = async (jobId, options = {}) => {
  try {
    return await getTalentCandidates(jobId, options);
  } catch (error) {
    const items = (recruitmentCandidatesData[jobId] || []).map((candidate) => ({
      ...candidate,
      dataSource: 'mock-fallback',
    }));
    return {
      items,
      total_candidates: items.length,
      method: 'mock-fallback',
      source: 'mock-fallback',
      stage_counts: {},
      retrieval_stats: {
        total_profiles: items.length,
        initial_recall_count: items.length,
        eligible_count: items.length,
        filtered_out_count: 0,
        threshold: options.minScore ?? 55,
        page: 1,
        page_size: items.length,
        total_pages: 1,
        took_ms: 0,
      },
      warning: error.message,
    };
  }
};
export const getCandidateExplanation = (jobId, candidateId, useLlm = true, minScore = 55) => (
  getTalentCandidateExplanation(jobId, candidateId, useLlm, minScore)
);
export const updateCandidateStage = async (jobId, candidateId, status) => {
  try {
    return await patchTalentCandidateStage(jobId, candidateId, status);
  } catch (error) {
    return { jobId, candidateId, status, source: 'local-session', warning: error.message };
  }
};
