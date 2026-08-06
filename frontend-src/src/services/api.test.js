import axios from 'axios';
import {
  createResumeSearchForm,
  healthCheck,
  rerankWithKeywords,
  searchJobsWithRerankingAndResume,
} from './api';

jest.mock('axios', () => ({
  __esModule: true,
  default: (() => {
    const mockApi = {
      post: jest.fn(),
      interceptors: {
        request: { use: jest.fn() },
        response: { use: jest.fn() },
      },
    };
    return {
      get: jest.fn(),
      create: () => mockApi,
      __mockApi: mockApi,
    };
  })(),
}));

const mockApiPost = axios.__mockApi.post;
const mockAxiosGet = axios.get;

describe('createResumeSearchForm', () => {
  beforeEach(() => jest.clearAllMocks());

  it('uses the backend multipart field contract', () => {
    const resume = new File(['resume'], 'resume.pdf', { type: 'application/pdf' });
    const form = createResumeSearchForm({
      query: 'React 前端工程师',
      location: '合肥',
      remote_allowed: false,
      required_skills: ['React', 'TypeScript'],
      preferred_skills: ['Three.js'],
      limit: 8,
    }, resume);

    expect(form.get('resume_file')).toBe(resume);
    expect(form.get('query')).toBe('React 前端工程师');
    expect(form.get('location')).toBe('合肥');
    expect(form.get('remote_allowed')).toBe('false');
    expect(form.getAll('required_skills')).toEqual(['React', 'TypeScript']);
    expect(form.getAll('preferred_skills')).toEqual(['Three.js']);
    expect(form.get('limit')).toBe('8');
  });

  it('sends the keyword reranking field expected by the backend', async () => {
    mockApiPost.mockResolvedValue({ data: { jobs: [] } });

    await rerankWithKeywords([{ id: 'job-1' }], ['React']);

    expect(mockApiPost).toHaveBeenCalledWith('/reranking/rerank-with-keywords', {
      search_results: [{ id: 'job-1' }],
      selected_keywords: ['React'],
    }, expect.any(Object));
  });

  it('defaults missing reranking pagination fields', async () => {
    const resume = new File(['resume'], 'resume.pdf', { type: 'application/pdf' });
    mockApiPost.mockResolvedValue({ data: { jobs: [] } });

    await searchJobsWithRerankingAndResume({ query: 'React' }, resume);

    const formData = mockApiPost.mock.calls[0][1];
    expect(formData.get('page')).toBe('1');
    expect(formData.get('page_size')).toBe('20');
  });

  it('checks the root health endpoint outside the API v1 prefix', async () => {
    mockAxiosGet.mockResolvedValue({ data: { status: 'healthy' } });

    await healthCheck();

    expect(mockAxiosGet).toHaveBeenCalledWith('/health');
  });
});
