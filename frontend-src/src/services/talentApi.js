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
import { getJobById, getJobRecommendations, uploadResume } from './api';

export const TALENT_API_CAPABILITIES = Object.freeze({
  resumeDiagnosis: 'live',
  capabilityGraph: 'mock-only',
  learningPlan: 'mock-only',
  recruitment: 'mock-only',
  candidatePipeline: 'mock-only',
  marketSignals: 'mock-only',
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
export const getCapabilityGraph = () => mockOnly(graphData);
export const getRoleEvolution = () => mockOnly(evolutionData);
const fitLabels = {
  excellent: '高度匹配',
  good: '较为匹配',
  fair: '部分匹配',
  poor: '匹配度较低',
};

const toPercent = (score) => Math.round(Math.max(0, Math.min(1, Number(score) || 0)) * 100);

const normalizeLiveDiagnosis = (candidateProfile, recommendations, jobs) => {
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
  };
};

const diagnoseUploadedResume = async (resumeFile) => {
  const candidateProfile = await uploadResume(resumeFile);
  const recommendations = await getJobRecommendations(candidateProfile.candidate);
  if (!recommendations.length) {
    throw new Error('简历解析成功，但当前岗位库中没有可用的匹配结果');
  }

  const jobResults = await Promise.allSettled(
    recommendations.slice(0, 3).map((match) => getJobById(match.job_id))
  );
  const jobs = jobResults.map((result) => result.status === 'fulfilled' ? result.value : null);
  return normalizeLiveDiagnosis(candidateProfile, recommendations, jobs);
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
export const getRecruitmentJobs = () => mockOnly(recruitmentJobsData);
export const saveRecruitmentJob = (job) => mockOnly(job);
export const getJobCandidates = (jobId) => mockOnly(recruitmentCandidatesData[jobId] || []);
export const updateCandidateStage = (jobId, candidateId, status) => mockOnly(
  { jobId, candidateId, status }
);
