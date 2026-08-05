jest.mock('axios', () => {
  const mockApi = { post: jest.fn(), get: jest.fn() };
  return {
    __esModule: true,
    default: { create: () => mockApi, __mockApi: mockApi },
  };
});

import axios from 'axios';
import {
  analyzeKnowledgeGraphGap,
  getMarketRuntime,
  ingestMarketCsv,
  rerankSemantic,
  searchBm25,
} from './intelligenceApi';

const mockPost = axios.__mockApi.post;
const mockGet = axios.__mockApi.get;

describe('intelligenceApi contracts', () => {
  beforeEach(() => jest.clearAllMocks());

  it('uses the canonical diagnosis endpoint contracts', async () => {
    mockPost
      .mockResolvedValueOnce({ data: { hits: [] } })
      .mockResolvedValueOnce({ data: { candidates: [] } })
      .mockResolvedValueOnce({ data: { job_id: 'job-1' } });

    await searchBm25('React TypeScript', { size: 8 });
    await rerankSemantic({ queryId: 'candidate-1', queryText: 'React', candidates: [] });
    await analyzeKnowledgeGraphGap('candidate-1', 'job-1');

    expect(mockPost).toHaveBeenNthCalledWith(1, '/bm25/search', expect.objectContaining({ query: 'React TypeScript', size: 8 }));
    expect(mockPost).toHaveBeenNthCalledWith(2, '/semantic/rerank', {
      query_id: 'candidate-1',
      query_text: 'React',
      candidates: [],
    });
    expect(mockPost).toHaveBeenNthCalledWith(3, '/kg/analyze', {
      candidate_id: 'candidate-1',
      job_id: 'job-1',
    });
  });

  it('reports partial market runtime availability', async () => {
    mockGet
      .mockResolvedValueOnce({ data: { total_jobs_elasticsearch: 120 } })
      .mockRejectedValueOnce(new Error('BM25 unavailable'));

    await expect(getMarketRuntime()).resolves.toEqual({
      ingestion: { total_jobs_elasticsearch: 120 },
      bm25: null,
      available: true,
    });
  });

  it('uses the backend CSV multipart contract', async () => {
    const file = new File(['title,skills'], 'market.csv', { type: 'text/csv' });
    mockPost.mockResolvedValue({ data: { status: 'processing' } });

    await ingestMarketCsv(file);

    const [, formData] = mockPost.mock.calls[0];
    expect(mockPost.mock.calls[0][0]).toBe('/csv/ingest-csv');
    expect(formData.get('file')).toBe(file);
    expect(formData.get('index_to_elasticsearch')).toBe('true');
    expect(formData.get('create_neo4j_nodes')).toBe('true');
    expect(formData.get('process_with_nlp')).toBe('true');
    expect(formData.get('batch_size')).toBe('100');
  });
});
