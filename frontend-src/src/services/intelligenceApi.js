import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

const detail = (error, fallback) => {
  const value = error.response?.data?.detail;
  if (Array.isArray(value)) return value.map((item) => item.msg).filter(Boolean).join('；') || fallback;
  return value || fallback;
};

export const searchBm25 = async (query, options = {}) => {
  try {
    const response = await api.post('/bm25/search', {
      query,
      size: options.size || 8,
      source_type: options.sourceType || null,
      location: options.location || null,
      exclude_duplicates: options.excludeDuplicates !== false,
    });
    return response.data;
  } catch (error) {
    throw new Error(detail(error, 'BM25 岗位召回失败'));
  }
};

export const rerankSemantic = async ({ queryId, queryText, candidates }) => {
  try {
    const response = await api.post('/semantic/rerank', {
      query_id: queryId,
      query_text: queryText,
      candidates,
    });
    return response.data;
  } catch (error) {
    throw new Error(detail(error, '语义重排失败'));
  }
};

export const analyzeKnowledgeGraphGap = async (candidateId, jobId) => {
  try {
    const response = await api.post('/kg/analyze', {
      candidate_id: candidateId,
      job_id: jobId,
    });
    return response.data;
  } catch (error) {
    throw new Error(detail(error, '知识图谱差距分析失败'));
  }
};

export const getMarketRuntime = async () => {
  const [ingestion, bm25] = await Promise.allSettled([
    api.get('/ingestion/stats'),
    api.get('/bm25/stats'),
  ]);

  return {
    ingestion: ingestion.status === 'fulfilled' ? ingestion.value.data : null,
    bm25: bm25.status === 'fulfilled' ? bm25.value.data : null,
    available: ingestion.status === 'fulfilled' || bm25.status === 'fulfilled',
  };
};

export const ingestMarketCsv = async (file) => {
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('index_to_elasticsearch', 'true');
    formData.append('create_neo4j_nodes', 'true');
    formData.append('process_with_nlp', 'true');
    formData.append('batch_size', '100');

    const response = await api.post('/csv/ingest-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  } catch (error) {
    throw new Error(detail(error, '市场 JD 导入失败'));
  }
};
