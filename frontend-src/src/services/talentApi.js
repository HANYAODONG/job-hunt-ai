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
  ingestMarketCsv,
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
  recruitment: 'mock-only',
  candidatePipeline: 'mock-only',
  marketSignals: 'partial-live',
  marketDataIngestion: 'live',
  governance: 'mock-only',
  evaluation: 'mock-only',
});

const mockOnly = async (fallback) => fallback;

export const getTalentOverview = () => mockOnly(dashboardData);
export const getDiscoveryCandidates = () => mockOnly(discoveryCandidates);
export const getMarketChangeCandidates = () => mockOnly(marketChangeCandidates);
export const reviewDiscoveryCandidate = (id, decision) => mockOnly(
  { id, decision, status: decision === 'publish' ? '已发布' : '已退回' }
);
export const getCapabilityGraph = () => 
  fetch('/api/v1/graph').then(res => res.json());
export const getRoleEvolution = () => mockOnly(evolutionData);
const fitLabels = {
  excellent: '高度匹配',
  good: '较为匹配',
  fair: '部分匹配',
  poor: '匹配度较低',
};

const toPercent = (score) => Math.round(Math.max(0, Math.min(1, Number(score) || 0)) * 100);
const clampScore = (score) => Math.max(0, Math.min(1, Number(score) || 0));

const normalizeLiveDiagnosis = (candidateProfile, recommendations, jobs, pipelineWarning = null) => {
  const candidate = candidateProfile.candidate || {};
  const skills = candidateProfile.extracted_skills?.length
    ? candidateProfile.extracted_skills
    : (candidate.skills || []).map((skill) => skill.name).filter(Boolean);
  const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false });

  const matches = recommendations.slice(0, 3).map((recommendation, index) => {
    const job = jobs[index] || {};
    const matchingSkills = recommendation.matching_skills || [];
    const missingSkills = recommendation.missing_skills || [];
    const score = toPercent(recommendation.match_score);
    const requiredSkillCount = Math.max(1, (job.required_skills || []).length);
    const evidenceCoverage = Math.round((matchingSkills.length / requiredSkillCount) * 100);
    const currentEvidence = Math.max(0, Math.min(100, evidenceCoverage));
    const gaps = missingSkills.slice(0, 3).map((skill, gapIndex) => ({
      skill,
      priority: gapIndex < 2 ? '高' : '中',
      current: 0,
      target: 100,
      reason: `岗位要求包含“${skill}”，当前简历解析结果中未发现对应技能证据。`,
    }));

    return {
      id: recommendation.job_id,
      role: job.title || `岗位 ${index + 1}`,
      family: job.job_family || job.company_name || '岗位库',
      company: job.company_name || '',
      version: '当前 JD',
      score,
      reason: matchingSkills.length
        ? `${fitLabels[recommendation.overall_fit] || '已完成匹配'}，已识别 ${matchingSkills.slice(0, 4).join('、')} 等技能证据。`
        : `${fitLabels[recommendation.overall_fit] || '已完成匹配'}，当前结果主要基于经历与岗位语义相关度。`,
      gaps,
      matchingSkills,
      evidenceCoverage: currentEvidence,
      job,
    };
  });

  return {
    source: 'live',
    generatedAt,
    profile: {
      name: candidate.name || '未识别姓名',
      target: matches[0]?.role || '待确认岗位',
      confidence: null,
      skills,
      experience: candidateProfile.experience_summary
        || `已解析 ${candidate.experience?.length || 0} 段工作或项目经历。`,
    },
    matches,
    gaps: matches[0]?.gaps || [],
    pipeline: {
      mode: pipelineWarning ? 'legacy-fallback' : 'legacy',
      warning: pipelineWarning,
      capabilities: ['简历解析', '旧版岗位推荐'],
    },
  };
};

const buildCandidateQuery = (candidateProfile) => {
  const candidate = candidateProfile.candidate || {};
  const skills = candidateProfile.extracted_skills?.length
    ? candidateProfile.extracted_skills
    : (candidate.skills || []).map((skill) => skill.name).filter(Boolean);
  const experience = (candidate.experience || []).flatMap((item) => [item.position, item.description]).filter(Boolean);

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
  const skills = candidateProfile.extracted_skills?.length
    ? candidateProfile.extracted_skills
    : (candidate.skills || []).map((skill) => skill.name).filter(Boolean);
  const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false });

  const matches = fusionResults.slice(0, 3).map((result, index) => {
    const hit = hitByJobId.get(result.job_id) || {};
    const gap = gapByJobId.get(result.job_id) || {};
    const matchingSkills = gap.matched_skills || [];
    const missingSkills = result.missing_skills || gap.missing_skills || [];

    return {
      id: result.job_id,
      role: hit.standard_job || hit.title || `岗位 ${index + 1}`,
      family: hit.job_family || hit.standard_category || '岗位库',
      company: hit.company || '',
      version: '图谱当前版本',
      score: toPercent(result.final_score),
      reason: result.explanation || `已完成关键词、语义与知识图谱多因子融合排序，当前排名第 ${result.rank || index + 1}。`,
      gaps: missingSkills.slice(0, 3).map((skill, gapIndex) => ({
        skill,
        priority: gapIndex < 2 ? '高' : '中',
        current: 0,
        target: 100,
        reason: `知识图谱显示岗位要求“${skill}”，当前候选人节点未关联该技能。`,
      })),
      matchingSkills,
      evidenceCoverage: toPercent(gap.skill_coverage),
      evidencePaths: result.evidence_paths || gap.evidence_paths || [],
      scoreBreakdown: result.score_breakdown || null,
      job: {
        id: result.job_id,
        title: hit.title,
        standard_job: hit.standard_job,
        company_name: hit.company,
        job_family: hit.job_family,
        required_skills: gap.job_required_skills || hit.skills || [],
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
      name: candidate.name || '未识别姓名',
      target: matches[0]?.role || '待确认岗位',
      confidence: null,
      skills,
      experience: candidateProfile.experience_summary
        || `已解析 ${candidate.experience?.length || 0} 段工作或项目经历。`,
    },
    matches,
    gaps: matches[0]?.gaps || [],
    pipeline: {
      mode: 'full',
      warning: null,
      capabilities: ['BM25 召回', 'Semantic 重排', '知识图谱差距分析', 'Fusion 融合排序'],
    },
  };
};

const runFullDiagnosisPipeline = async (candidateProfile) => {
  const candidateId = candidateProfile.candidate?.id;
  const queryText = buildCandidateQuery(candidateProfile);
  if (!candidateId || !queryText) throw new Error('简历画像缺少候选人 ID 或可检索文本');

  const bm25Result = await searchBm25(queryText, { size: 8 });
  const hits = (bm25Result.hits || []).filter((hit) => hit.job_id);
  if (!hits.length) throw new Error('BM25 岗位索引没有返回候选岗位');

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
    throw new Error('BM25 岗位与知识图谱岗位 ID 尚未对齐，无法形成完整差距分析');
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
      missing_skills: gap.missing_skills || [],
      evidence_paths: gap.evidence_paths || [],
    };
  });
  const fusionResult = await rankJobs(candidateId, fusionInputs);
  if (!fusionResult.results?.length) throw new Error('融合排序没有返回匹配结果');

  return normalizeFullDiagnosis(candidateProfile, hits, gapByJobId, fusionResult.results);
};

const diagnoseUploadedResume = async (resumeFile) => {
  const candidateProfile = await uploadResume(resumeFile);
  try {
    return await runFullDiagnosisPipeline(candidateProfile);
  } catch (pipelineError) {
    const recommendations = await getJobRecommendations(candidateProfile.candidate);
    if (!recommendations.length) {
      throw new Error(`简历解析成功，但完整匹配链路不可用且旧岗位库没有结果：${pipelineError.message}`);
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
export const getLiveMarketTrend = (skill) => getMarketTrends(skill);
export const getMarketRuntimeStatus = () => getMarketRuntime();
export const importMarketCsv = (file) => ingestMarketCsv(file);
export const getRecruitmentJobs = () => mockOnly(recruitmentJobsData);
export const saveRecruitmentJob = (job) => mockOnly(job);
export const getJobCandidates = (jobId) => mockOnly(recruitmentCandidatesData[jobId] || []);
export const updateCandidateStage = (jobId, candidateId, status) => mockOnly(
  { jobId, candidateId, status }
);
