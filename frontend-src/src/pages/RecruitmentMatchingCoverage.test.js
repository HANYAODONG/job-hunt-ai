import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App as AntdApp } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';

jest.mock('../services/talentApi', () => ({
  getRecruitmentJobs: jest.fn(),
  saveRecruitmentJob: jest.fn(),
  getJobCandidates: jest.fn(),
  getCandidateExplanation: jest.fn(),
  updateCandidateStage: jest.fn(),
}));
jest.mock('../services/graphSync', () => ({ notifyGraphDataChanged: jest.fn() }));

import {
  getCandidateExplanation,
  getJobCandidates,
  getRecruitmentJobs,
  saveRecruitmentJob,
  updateCandidateStage,
} from '../services/talentApi';
import RecruitmentJobsPage from './RecruitmentJobsPage';
import CandidateMatchingPage from './CandidateMatchingPage';

const job = {
  id: 'JD-001', title: '大模型应用工程师', department: 'AI 平台部', location: '合肥',
  employmentType: '全职', status: '招聘中', version: 'JD v1.0', roleVersion: '大模型应用工程师 v2',
  publishedAt: '昨天', updatedAt: '昨天', openings: 2, applications: 3, newApplications: 1,
  sourceType: 'enterprise', dataSource: 'live-standard-dataset', summary: '负责企业级 Agent 应用研发。',
  responsibilities: ['研发 RAG 服务', '建设评测闭环'],
  requiredSkills: [{ name: 'Python', level: 80 }], bonusSkills: [],
  revisions: [{ version: 'v1.0', date: '昨天', note: '初始发布' }],
  marketSuggestion: { title: '补充 Agent 工具调用', detail: '市场需求增长', confidence: 90, evidence: 12 },
};

const candidatesResult = {
  items: [
    { id: 'C-001', name: '张三', retrievalRank: 1, decisionBand: '强匹配', score: 91, confidence: 94, isEligible: true, status: '待筛选', degree: '硕士', experience: '3 年', location: '合肥', summary: '具备 RAG 项目经验。', dimensions: [{ label: '技能', value: 95 }], matchedSkills: ['Python', 'RAG'], gaps: ['Agent 评测'], evidence: ['简历项目使用向量检索'], resume: '张三.pdf' },
    { id: 'C-002', name: '李四', retrievalRank: 2, decisionBand: '需复核', score: 48, confidence: 78, isEligible: false, status: '不匹配', degree: '本科', experience: '1 年', location: '北京', summary: '基础开发经验。', dimensions: [{ label: '技能', value: 48 }], matchedSkills: ['Python'], gaps: ['RAG', 'Agent'], evidence: ['课程项目'], resume: '李四.pdf' },
  ],
  source: 'live', method: 'rrf_bm25_text2vec_neo4j', stage_counts: { '待筛选': 1, '不匹配': 1 },
  retrieval_stats: { total_profiles: 100, initial_recall_count: 40, reranked_count: 20, eligible_count: 1, filtered_out_count: 1, threshold: 55, recommended_threshold: 60, page: 1, page_size: 50, total_pages: 1, took_ms: 31, score_min: 48, score_max: 91 },
};

const wrap = (ui, entry = '/') => (
  <AntdApp><MemoryRouter initialEntries={[entry]}><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider></MemoryRouter></AntdApp>
);

beforeAll(() => {
  window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() });
  window.HTMLElement.prototype.scrollTo = jest.fn();
});

beforeEach(() => {
  getRecruitmentJobs.mockResolvedValue({ items: [job], total: 1, source: 'live' });
  saveRecruitmentJob.mockImplementation(async (value) => value);
  getJobCandidates.mockResolvedValue(candidatesResult);
  getCandidateExplanation.mockResolvedValue({ mode: 'deepseek_grounded_rag_v1', conclusion: '候选人可进入面试', summary: 'Python 与 RAG 证据充分', matched_evidence: ['RAG 项目'], skill_gaps: ['Agent 评测'], risks: [], interview_questions: ['介绍检索方案'] });
  updateCandidateStage.mockResolvedValue({});
});

afterEach(() => jest.clearAllMocks());

describe('candidate matching review', () => {
  it('renders the thresholded retrieval workspace for a selected job', async () => {
    render(wrap(<CandidateMatchingPage />, '/candidates?job=JD-001'));
    await waitFor(() => expect(screen.getAllByText('张三').length).toBeGreaterThan(0));
    expect(screen.getByText('BM25 + text2vec + Neo4j RRF')).toBeTruthy();
    expect(screen.getByText('准入规则')).toBeTruthy();
    expect(screen.getByText('生成证据解释')).toBeTruthy();
    expect(getJobCandidates).toHaveBeenCalledWith('JD-001', expect.objectContaining({ minScore: 60 }));
  });
});
