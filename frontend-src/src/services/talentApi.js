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
export const reviewDiscoveryCandidate = (id, decision) => mockOnly({
  id,
  decision,
  status: decision === 'publish' ? 'published' : 'rejected',
});
export const getCapabilityGraph = () => mockOnly(graphData);
export const getRoleEvolution = () => mockOnly(evolutionData);

const fitLabels = {
  excellent: 'excellent match',
  good: 'good match',
  fair: 'partial match',
  poor: 'weak match',
};

const toPercent = (score) => Math.round(Math.max(0, Math.min(1, Number(score) || 0)) * 100);
const clampScore = (score) => Math.max(0, Math.min(1, Number(score) || 0));

const extractSkills = (candidateProfile) => {
  const candidate = candidateProfile.candidate || {};
  return candidateProfile.extracted_skills?.length
    ? candidateProfile.extracted_skills
    : (candidate.skills || []).map((skill) => skill.name).filter(Boolean);
};

const makeGapItems = (skills, sourceLabel) => skills.slice(0, 3).map((skill, gapIndex) => ({
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
    const matchingSkills = recommendation.matching_skills || [];
    const missingSkills = recommendation.missing_skills || [];
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
    const matchingSkills = gap.matched_skills || [];
    const missingSkills = result.missing_skills || gap.missing_skills || [];

    return {
      id: result.job_id,
      role: hit.standard_job || hit.title || `Job ${index + 1}`,
      family: hit.job_family || hit.standard_category || 'job family pending',
      company: hit.company || '',
      version: 'current graph version',
      score: toPercent(result.final_score),
      reason: result.explanation || `Ranked by BM25, semantic rerank, knowledge graph gap analysis, and fusion scoring. Current rank: ${result.rank || index + 1}.`,
      gaps: makeGapItems(missingSkills, 'The knowledge graph'),
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
      missing_skills: gap.missing_skills || [],
      evidence_paths: gap.evidence_paths || [],
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
export const getLiveMarketTrend = (skill) => getMarketTrends(skill);
export const getMarketRuntimeStatus = () => getMarketRuntime();
export const importMarketCsv = (file) => ingestMarketCsv(file);
export const getRecruitmentJobs = () => mockOnly(recruitmentJobsData);
export const saveRecruitmentJob = (job) => mockOnly(job);
export const getJobCandidates = (jobId) => mockOnly(recruitmentCandidatesData[jobId] || []);
export const updateCandidateStage = (jobId, candidateId, status) => mockOnly({
  jobId,
  candidateId,
  status,
});
