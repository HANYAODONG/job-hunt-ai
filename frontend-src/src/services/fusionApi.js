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
