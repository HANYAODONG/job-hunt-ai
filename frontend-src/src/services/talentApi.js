import {
  dashboardData,
  diagnosisData,
  discoveryCandidates,
  evaluationData,
  evolutionData,
  governanceData,
  graphData,
  learningPlanData,
  marketChangeCandidates,
  roleCatalogData,
} from '../data/mockTalentData';
import { recruitmentCandidatesData, recruitmentJobsData } from '../data/mockRecruitmentData';
import { getJobById, getJobRecommendations, getMarketTrends, uploadResume } from './api';
import {
  analyzeKnowledgeGraphGap,
  getMarketRuntime,
  getTalentCandidates,
  getTalentCandidateExplanation,
  getTalentJobs,
  getTalentMarketStats,
  ingestMarketCsv,
  patchTalentCandidateStage,
  putTalentJob,
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
  capabilityGraph: 'mock-only',
  learningPlan: 'mock-only',
  recruitment: 'live-with-fallback',
  candidatePipeline: 'live-with-fallback',
  marketSignals: 'partial-live',
  marketDataIngestion: 'live',
  governance: 'mock-only',
  evaluation: 'mock-only',
});

const mockOnly = async (fallback) => fallback;

export const getTalentOverview = () => mockOnly(dashboardData);
export const getDiscoveryCandidates = () => mockOnly(discoveryCandidates);
export const getMarketChangeCandidates = () => mockOnly(marketChangeCandidates);
export const reviewDiscoveryCandidate = (id, decision) => mockOnly({
  id,
  decision,
  status: decision === 'publish' ? 'published' : 'rejected',
});

export const getCapabilityGraph = (year) => {
  const url = year ? `/api/v1/graph?year=${year}` : '/api/v1/graph';
  return fetch(url)
    .then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .catch(() => {
      console.warn('Graph API is unavailable; using mock graph data.');
      return mockOnly(graphData);
    });
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
      role: hit.standard_job || hit.title || `Job ${index + 1}`,
      family: hit.job_family || hit.standard_category || 'job family pending',
      company: hit.company || '',
      version: 'current graph version',
      score: toPercent(result.final_score),
      reason: toDisplayText(result.explanation) || `Ranked by BM25, semantic rerank, knowledge graph gap analysis, and fusion scoring. Current rank: ${result.rank || index + 1}.`,
      gaps: makeGapItems(missingSkills, 'The knowledge graph'),
      matchingSkills,
      evidenceCoverage: toPercent(gap.skill_coverage),
      evidencePaths: normalizeTextList(result.evidence_paths || gap.evidence_paths),
      scoreBreakdown: result.score_breakdown || null,
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

const runFullDiagnosisPipeline = async (candidateProfile) => {
  const candidateId = candidateProfile.candidate?.id;
  const queryText = buildCandidateQuery(candidateProfile);
  if (!candidateId || !queryText) throw new Error('Resume profile lacks candidate id or searchable text.');

  const bm25Result = await searchBm25(queryText, { size: 8 });
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
    };
  });
  const fusionResult = await rankJobs(candidateId, fusionInputs);
  if (!fusionResult.results?.length) throw new Error('Fusion ranking returned no results.');

  return normalizeFullDiagnosis(candidateProfile, hits, gapByJobId, fusionResult.results);
};

const diagnoseUploadedResume = async (resumeFile) => {
  const candidateProfile = await uploadResume(resumeFile);
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
export const diagnoseCandidate = ({ resumeFile } = {}) => {
  if (!resumeFile || process.env.REACT_APP_USE_RESUME_MOCK === 'true') return Promise.resolve(diagnosisData);
  return diagnoseUploadedResume(resumeFile);
};
export const getDataGovernance = () => mockOnly(governanceData);
export const getEvaluationReport = () => mockOnly(evaluationData);
export const getRoleCatalog = () => mockOnly(roleCatalogData);
export const getLearningPlan = () => mockOnly(learningPlanData);

const roleEvolutionApiUrl = process.env.REACT_APP_ROLE_EVOLUTION_API_URL;

const roleEvolutionRequest = async (path, options = {}) => {
  if (!roleEvolutionApiUrl) throw new Error('岗位演化服务未配置');
  const response = await fetch(`${roleEvolutionApiUrl.replace(/\/$/, '')}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`岗位演化服务请求失败（${response.status}）`);
  return response.json();
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
  if (!roleEvolutionApiUrl) return fallback;
  try {
    const [overview, jobs, reviewItems, optimization] = await Promise.all([
      roleEvolutionRequest('/api/analytics/overview?domain=company'),
      roleEvolutionRequest('/api/analytics/jobs?domain=company'),
      roleEvolutionRequest('/api/review/items?domain=company'),
      roleEvolutionRequest(`/api/optimization/profile?domain=company&standard_job=${encodeURIComponent(fallback.analytics.role)}`),
    ]);
    const jobNames = Array.isArray(jobs) ? jobs : [];
    const profileRows = Array.isArray(optimization?.skills) ? optimization.skills : [];
    return {
      ...fallback,
      jobs: jobNames.length ? jobNames.map((name) => ({ name, summary: '来自岗位技能演化数据源的岗位画像。', requiredSkills: [] })) : fallback.jobs,
      pending: Array.isArray(reviewItems) ? reviewItems : fallback.pending,
      analytics: { ...fallback.analytics, ...(overview || {}) },
      optimization: profileRows.length ? { ...fallback.optimization, requiredSkills: profileRows.map((skill) => ({ name: skill.skill || skill.normalized_skill || skill })) } : fallback.optimization,
    };
  } catch {
    return fallback;
  }
};

export const submitRoleJd = async (payload) => {
  try {
    return roleEvolutionApiUrl
      ? await roleEvolutionRequest('/api/jobs/submit-one-dry-run?domain=company', { method: 'POST', body: JSON.stringify(payload) })
      : { effectId: 'EV-20260725-01', status: '待审核', ...roleEvolutionFallback().latest, input: payload };
  } catch {
    return { effectId: 'EV-20260725-01', status: '待审核', ...roleEvolutionFallback().latest, input: payload };
  }
};

export const getLiveEvolution = async (effectId) => {
  try {
    return roleEvolutionApiUrl
      ? await roleEvolutionRequest(`/api/live-evolution/${encodeURIComponent(effectId)}?domain=company`)
      : roleEvolutionFallback().latest;
  } catch {
    return roleEvolutionFallback().latest;
  }
};

export const getRoleAnalytics = async (params = {}) => {
  try {
    if (roleEvolutionApiUrl) {
      const query = new URLSearchParams({ domain: 'company', ...params }).toString();
      const [overview, trend, lifecycle, migration, profileCompare] = await Promise.all([
        roleEvolutionRequest(`/api/analytics/overview?${query}`),
        roleEvolutionRequest(`/api/analytics/job-trend?${query}`),
        roleEvolutionRequest(`/api/analytics/lifecycle?${query}`),
        roleEvolutionRequest(`/api/analytics/skill-migration?${query}`),
        roleEvolutionRequest(`/api/analytics/profile-compare?${query}`),
      ]);
      return { overview, trend, lifecycle, migration, profileCompare };
    }
    return roleEvolutionFallback().analytics;
  } catch {
    return roleEvolutionFallback().analytics;
  }
};

export const saveRoleOptimization = async (payload) => {
  try {
    return roleEvolutionApiUrl
      ? await roleEvolutionRequest('/api/optimization/overrides?domain=company', { method: 'POST', body: JSON.stringify(payload) })
      : { status: '已保存', version: 'v1.3', ...payload };
  } catch {
    return { status: '已保存', version: 'v1.3', ...payload };
  }
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
