/**
 * Fusion API Service — 工作流4 融合排序 API 调用
 */

import axios from 'axios';
import { generateMockFusionResults } from '../data/mockFusionData';

const API_BASE_URL = process.env.REACT_APP_API_URL || '/api/v1';
const USE_MOCK = process.env.REACT_APP_USE_MOCK_DATA === 'true';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

/**
 * 获取 Mock 融合排序结果（不依赖后端）
 */
export async function getMockRankedResults(queryId, numJobs = 20, seed = null, weights = null, layeredWeights = null) {
  if (!USE_MOCK) {
    try {
      const response = await api.post('/fusion/mock-rank', {
        query_id: queryId || 'mock_resume_001',
        num_jobs: numJobs,
        seed: seed,
        layered_weights: layeredWeights,
      });
      return response.data;
    } catch (err) {
      console.warn('Backend /fusion/mock-rank unreachable, using local mock:', err.message);
    }
  }
  return generateMockFusionResults(queryId, numJobs, seed || Date.now(), weights);
}

/**
 * 查询驱动融合排序（真实 BM25 + 分层融合）
 */
export async function rankFromQuery(queryText, options = {}) {
  const { queryId = null, size = 20, layeredWeights = null, sourceType = null } = options;
  const response = await api.post('/fusion/rank-from-query', {
    query_text: queryText,
    query_id: queryId,
    size,
    layered_weights: layeredWeights,
    source_type: sourceType,
  });
  return response.data;
}

/**
 * 前端统一推荐入口：后端负责组织 BM25 / Semantic / KG / Fusion 链路。
 */
export async function recommendJobs(options = {}) {
  const {
    candidateId = null,
    queryText = null,
    topK = 20,
    candidatePool = 100,
    mode = 'sample',
    sourceType = null,
    layeredWeights = null,
  } = options;

  const response = await api.post('/fusion/recommend', {
    candidate_id: candidateId,
    query_text: queryText,
    top_k: topK,
    candidate_pool: candidatePool,
    mode,
    source_type: sourceType,
    layered_weights: layeredWeights,
  });
  return response.data;
}

/**
 * 批量融合排序（传真实数据）
 */
export async function rankJobs(queryId, fusionInputs) {
  const response = await api.post('/fusion/rank', {
    query_id: queryId,
    jobs: fusionInputs,
  });
  return response.data;
}

/**
 * 单条融合评分
 */
export async function scoreSingle(fusionInput) {
  const response = await api.post('/fusion/score', fusionInput);
  return response.data;
}

/**
 * 获取当前服务端融合权重
 */
export async function getWeights() {
  const response = await api.get('/fusion/weights');
  return response.data;
}

/**
 * 更新服务端融合权重（旧格式）
 */
export async function updateWeights(weights) {
  const response = await api.put('/fusion/weights', weights);
  return response.data;
}

/**
 * 恢复默认权重
 */
export async function resetWeights() {
  const response = await api.post('/fusion/weights/reset');
  return response.data;
}

/**
 * 获取分层融合权重（v2）
 */
export async function getLayeredWeights() {
  const response = await api.get('/fusion/weights/layered');
  return response.data;
}

/**
 * 更新分层融合权重（v2）
 */
export async function updateLayeredWeights(lw) {
  const response = await api.put('/fusion/weights/layered', lw);
  return response.data;
}

/**
 * 加载离线融合排序结果（从 artifacts/fusion_ranking/）
 * @param {string|null} queryId - 指定 query_id，不传则列出所有可用的
 * @param {string} preset - 融合预设: full, bm25-only, bm25-semantic, bm25-semantic-skill
 */
export async function loadFusionResults(queryId = null, preset = 'full') {
  const params = { preset };
  if (queryId) params.query_id = queryId;
  const response = await api.get('/fusion/load-results', { params });
  return response.data;
}
