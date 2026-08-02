/**
 * Fusion API Service — 工作流4 融合排序 API 调用
 */

import axios from 'axios';
import { generateMockFusionResults } from '../data/mockFusionData';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
const USE_MOCK = process.env.REACT_APP_USE_MOCK_DATA === 'true';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

/**
 * 获取 Mock 融合排序结果（不依赖后端）
 */
export async function getMockRankedResults(queryId, numJobs = 20, seed = null, weights = null) {
  // 如果后端可达且不是强制 mock 模式，优先调真实接口
  if (!USE_MOCK) {
    try {
      const response = await api.post('/fusion/mock-rank', {
        query_id: queryId || 'mock_resume_001',
        num_jobs: numJobs,
        seed: seed,
        weights: weights,
      });
      return response.data;
    } catch (err) {
      console.warn('Backend /fusion/mock-rank unreachable, using local mock:', err.message);
    }
  }
  // 降级到纯前端 mock（传入 weights 以影响本地计算）
  return generateMockFusionResults(queryId, numJobs, seed || Date.now(), weights);
}

/**
 * 查询驱动融合排序（真实 BM25）
 * 输入查询文本，后端自动调 BM25 → 归一化 → 融合
 */
export async function rankFromQuery(queryText, options = {}) {
  const { queryId = null, size = 20, weights = null, sourceType = null } = options;
  const response = await api.post('/fusion/rank-from-query', {
    query_text: queryText,
    query_id: queryId,
    size,
    weights,
    source_type: sourceType,
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
 * 更新服务端融合权重
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
