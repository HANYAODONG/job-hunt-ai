jest.mock('axios', () => {
  const client = {
    post: jest.fn(), get: jest.fn(), put: jest.fn(), delete: jest.fn(),
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
  };
  const axios = { create: jest.fn(() => client), get: jest.fn() };
  return { __esModule: true, default: axios, ...axios };
});
jest.mock('../data/mockJobData', () => ({ getMockSearchResults: jest.fn(), mockApiDelay: jest.fn() }));

import api, {
  applyToJob, bulkCreateJobs, createJob, createResumeSearchForm, deleteJob, extractKeywords,
  getCurrentUser, getJobById, getJobRecommendations, getMarketTrends, getPersonalizedRecommendations,
  getRerankingExplanation, getRerankingStatistics, getRerankingWeights, getResumeInsights,
  getSimilarJobs, getUserApplications, healthCheck, loginUser, registerUser, rerankWithKeywords,
  searchJobs, searchJobsWithReranking, searchJobsWithRerankingAndResume, searchJobsWithResume,
  updateJob, updateRerankingWeights, uploadResume,
} from './api';

beforeEach(() => {
  api.post.mockResolvedValue({ data: { ok: true } });
  api.get.mockResolvedValue({ data: { ok: true } });
  api.put.mockResolvedValue({ data: { ok: true } });
  api.delete.mockResolvedValue({ data: { ok: true } });
  jest.requireMock('axios').default.get.mockResolvedValue({ data: { status: 'ok' } });
});
afterEach(() => jest.clearAllMocks());

it('builds resume search form data and uses the search contracts', async () => {
  const resume = new File(['resume'], 'resume.pdf', { type: 'application/pdf' });
  const params = { query: 'Python', location: '合肥', min_salary: 1, remote_allowed: true, required_skills: ['Python'], preferred_skills: ['RAG'] };
  const form = createResumeSearchForm(params, resume);
  expect([...form.entries()]).toEqual(expect.arrayContaining([['query', 'Python'], ['location', '合肥'], ['required_skills', 'Python']]));
  await searchJobs(params);
  await searchJobsWithResume(params, resume);
  await searchJobsWithReranking(params, 'RAG', true);
  await searchJobsWithRerankingAndResume({ ...params, page: 2, page_size: 10 }, resume, 'RAG', true);
  await getPersonalizedRecommendations(resume, 'Agent', 5, false);
  expect(api.post).toHaveBeenCalledWith('/jobs/search', params, expect.any(Object));
  expect(api.post).toHaveBeenCalledWith('/jobs/search-with-resume', expect.any(FormData), expect.any(Object));
  expect(api.post).toHaveBeenCalledWith(expect.stringContaining('/reranking/search-reranked?user_description=RAG&include_explanations=true'), { search_query: params }, expect.any(Object));
  expect(api.post).toHaveBeenCalledWith('/reranking/personalized-recommendations', expect.any(FormData), expect.any(Object));
});

it('uses job, resume, management, ranking and auth API contracts', async () => {
  await getJobById('j1'); await getSimilarJobs('j1', 3); await uploadResume(new File(['x'], 'a.pdf'));
  await getResumeInsights('c1'); await getJobRecommendations({ id: 'c1' }); await getMarketTrends('Python');
  await createJob({ title: '岗位' }); await updateJob('j1', { title: '新岗位' }); await deleteJob('j1'); await bulkCreateJobs([]);
  await getRerankingExplanation('j1', 'Python'); await getRerankingWeights(); await updateRerankingWeights({ a: 1 }); await getRerankingStatistics();
  await registerUser({ email: 'a@example.com' }); await loginUser({ email: 'a@example.com' }); await getCurrentUser('token');
  await applyToJob('j1', { note: 'hi' }, 'token'); await getUserApplications('token'); await extractKeywords('Python'); await rerankWithKeywords({ jobs: [] }, { skills: ['Python'] }); await healthCheck();
  expect(api.get).toHaveBeenCalledWith('/jobs/j1');
  expect(api.put).toHaveBeenCalledWith('/jobs/j1', { title: '新岗位' });
  expect(api.delete).toHaveBeenCalledWith('/jobs/j1');
  expect(api.post).toHaveBeenCalledWith('/auth/apply/j1', { note: 'hi' }, expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer token' }) }));
  expect(api.post).toHaveBeenCalledWith('/keyword-extraction/extract', { query: 'Python' }, expect.any(Object));
  expect(jest.requireMock('axios').default.get).toHaveBeenCalledWith('/health');
});
