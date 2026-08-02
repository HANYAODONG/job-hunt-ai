import axios from 'axios';
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

const client = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1',
  timeout: 12000,
});

const useMock = process.env.REACT_APP_USE_TALENT_MOCK !== 'false';

const getOrMock = async (request, fallback) => {
  if (useMock) return fallback;

  try {
    const response = await request();
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const getTalentOverview = () => getOrMock(() => client.get('/talent-intelligence/overview'), dashboardData);
export const getDiscoveryCandidates = () => getOrMock(() => client.get('/talent-intelligence/discovery/candidates'), discoveryCandidates);
export const getMarketChangeCandidates = () => getOrMock(() => client.get('/talent-intelligence/discovery/changes'), marketChangeCandidates);
export const reviewDiscoveryCandidate = (id, decision) => getOrMock(
  () => client.post(`/talent-intelligence/discovery/candidates/${id}/review`, { decision }),
  { id, decision, status: decision === 'publish' ? '已发布' : '已退回' }
);
export const getCapabilityGraph = (params) => getOrMock(() => client.get('/talent-intelligence/capability-graph', { params }), graphData);
export const getRoleEvolution = (roleId) => getOrMock(() => client.get(`/talent-intelligence/roles/${roleId || 'llm-app-engineer'}/evolution`), evolutionData);
export const diagnoseCandidate = (payload) => getOrMock(() => client.post('/talent-intelligence/diagnosis', payload), diagnosisData);
export const getDataGovernance = () => getOrMock(() => client.get('/talent-intelligence/governance'), governanceData);
export const getEvaluationReport = () => getOrMock(() => client.get('/talent-intelligence/evaluation/report'), evaluationData);
export const getRoleCatalog = () => getOrMock(() => client.get('/talent-intelligence/roles'), roleCatalogData);
export const getLearningPlan = (profileId) => getOrMock(() => client.get(`/talent-intelligence/profiles/${profileId || 'demo-profile'}/learning-plan`), learningPlanData);
export const getRecruitmentJobs = () => getOrMock(() => client.get('/recruitment/jobs'), recruitmentJobsData);
export const saveRecruitmentJob = (job) => getOrMock(() => client.put(`/recruitment/jobs/${job.id}`, job), job);
export const getJobCandidates = (jobId) => getOrMock(() => client.get(`/recruitment/jobs/${jobId}/candidates`), recruitmentCandidatesData[jobId] || []);
export const updateCandidateStage = (jobId, candidateId, status) => getOrMock(
  () => client.patch(`/recruitment/jobs/${jobId}/candidates/${candidateId}`, { status }),
  { jobId, candidateId, status }
);
