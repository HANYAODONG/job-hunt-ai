import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App as AntdApp } from 'antd';
import { MemoryRouter } from 'react-router-dom';

jest.mock('axios', () => {
  const api = { post: jest.fn(), get: jest.fn(), put: jest.fn() };
  return { __esModule: true, default: { create: () => api, __mockApi: api } };
});

import axios from 'axios';
const mockApi = axios.__mockApi;

import {
  getMockRankedResults,
  rankFromQuery,
  recommendJobs,
  rankJobs,
  scoreSingle,
  getWeights,
  updateWeights,
  resetWeights,
  getLayeredWeights,
  updateLayeredWeights,
  loadFusionResults,
} from '../services/fusionApi';
import { notifyGraphDataChanged, subscribeGraphDataChanged } from '../services/graphSync';
import FusionScoreCard from './FusionScoreCard';
import RerankingScore from './RerankingScore';
import TechnicalInspector from './workbench/TechnicalInspector';

beforeAll(() => {
  if (!window.matchMedia) {
    window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() });
  }
});

describe('fusionApi and graph sync contracts', () => {
  beforeEach(() => jest.clearAllMocks());

  it('calls v2 fusion endpoints and preserves response data', async () => {
    mockApi.post.mockResolvedValue({ data: { ok: true } });
    mockApi.get.mockResolvedValue({ data: { weights: [] } });
    mockApi.put.mockResolvedValue({ data: { updated: true } });
    await rankFromQuery('Python', { queryId: 'r1', size: 5, sourceType: 'company' });
    await recommendJobs({ candidateId: 'c1', queryText: 'Python', topK: 3 });
    await rankJobs('r1', [{ job_id: 'j1' }]);
    await scoreSingle({ job_id: 'j1' });
    await getWeights();
    await updateWeights({ bm25: 1 });
    await resetWeights();
    await getLayeredWeights();
    await updateLayeredWeights({ role_gate: 0.3 });
    await loadFusionResults('r1', 'bm25-only');
    expect(mockApi.post).toHaveBeenCalledWith('/fusion/rank-from-query', expect.objectContaining({ query_text: 'Python', size: 5 }));
    expect(mockApi.post).toHaveBeenCalledWith('/fusion/recommend', expect.objectContaining({ candidate_id: 'c1', top_k: 3 }));
    expect(mockApi.get).toHaveBeenCalledWith('/fusion/load-results', { params: { preset: 'bm25-only', query_id: 'r1' } });
  });

  it('falls back to local mock data when mock endpoint is unavailable', async () => {
    mockApi.post.mockRejectedValue(new Error('offline'));
    const result = await getMockRankedResults('resume-1', 2, 42);
    expect(result).toBeTruthy();
    expect(result.results || result.jobs || result).toBeTruthy();
  });

  it('publishes custom and storage graph-sync events and unsubscribes', () => {
    const handler = jest.fn();
    const unsubscribe = subscribeGraphDataChanged(handler);
    notifyGraphDataChanged({ role: '后端开发工程师' });
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({ role: '后端开发工程师' }));
    window.dispatchEvent(new StorageEvent('storage', { key: 'job-hunt.graph-sync.v1', newValue: JSON.stringify({ source: 'storage' }) }));
    expect(handler).toHaveBeenCalledWith({ source: 'storage' });
    unsubscribe();
    const count = handler.mock.calls.length;
    notifyGraphDataChanged({ role: 'ignored' });
    expect(handler.mock.calls.length).toBe(count);
  });
});

const fusionResult = {
  job_id: 'j1',
  rank: 1,
  final_score: 0.82,
  score_breakdown: { bm25: 0.8, semantic_score: 0.7, skill_coverage: 0.9, graph: 0.3 },
  explanation: { reason: '技能与岗位方向匹配', matched_skills: ['Python'], missing_skills: ['Docker', 'SQL', '测试', '部署', '监控', '云'] },
  evidence_paths: ['candidate -> Python -> job'],
  meta: { title: '后端开发工程师', company: 'Acme', standard_job: '后端开发工程师', location: '北京', salary: '20K' },
};

describe('matching score UI components', () => {
  it('renders fusion score card, rank and expanded evidence details', () => {
    render(<AntdApp><FusionScoreCard result={fusionResult} rank={1} dataSources={{ bm25_score: 'real', semantic_score: 'pending' }} /></AntdApp>);
    expect(screen.getByText('后端开发工程师')).toBeTruthy();
    expect(screen.getByText('优秀')).toBeTruthy();
    fireEvent.click(screen.getByText('点击展开查看详情'));
    expect(screen.getByText(/得分明细/)).toBeTruthy();
    expect(screen.getByText(/知识图谱证据路径/)).toBeTruthy();
    expect(screen.getByText(/全部缺失技能/)).toBeTruthy();
  });

  it('loads reranking explanation and renders factor details', async () => {
    const onGetExplanation = jest.fn().mockResolvedValue({
      job_title: '后端开发工程师', company: 'Acme', final_score: 0.9, scoring_method: 'AI analysis',
      knowledge_graph_explanation: '技能路径接近', top_feature_attributions: ['Python'],
      factor_scores: { skill_match: { score: 0.9, weight: 0.4, contribution: 0.36, explanation: '技能覆盖高' } },
    });
    render(<AntdApp><RerankingScore score={0.9} showDetails jobId="j1" onGetExplanation={onGetExplanation} /></AntdApp>);
    expect(screen.getByText(/Match Score/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => expect(onGetExplanation).toHaveBeenCalledWith('j1'));
    expect(await screen.findByText('Why This Job Was Recommended')).toBeTruthy();
    expect(screen.getByText('技能路径接近')).toBeTruthy();
  });

  it('renders technical inspector tabs and structured evidence', () => {
    render(<TechnicalInspector title="岗位画像" status="已审核" version="v2" confidence={94} explanation={[{ reason: '匹配', matched_skills: ['Python'] }]} evidence={[{ source: 'JD', excerpt: '负责开发', confidence: '高' }]} history={[{ label: 'v2', time: '2026-09-01' }]} />);
    expect(screen.getByText(/匹配技能：Python/)).toBeTruthy();
    fireEvent.click(screen.getByRole('tab', { name: /证据/ }));
    expect(screen.getByText('负责开发')).toBeTruthy();
    fireEvent.click(screen.getByRole('tab', { name: /记录/ }));
    expect(screen.getAllByText('v2').length).toBeGreaterThan(0);
  });
});
