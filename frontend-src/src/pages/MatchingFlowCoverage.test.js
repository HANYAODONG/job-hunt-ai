import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App as AntdApp } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';

jest.mock('../services/talentApi', () => ({ diagnoseCandidate: jest.fn() }));
jest.mock('../services/fusionApi', () => ({ recommendJobs: jest.fn() }));
jest.mock('../services/api', () => ({ uploadResume: jest.fn() }));
jest.mock('../contexts/CandidateContext', () => ({
  useCandidate: jest.fn(),
}));
jest.mock('../components/workbench/TechnicalInspector', () => () => <div data-testid="technical-inspector">inspector</div>);

import { diagnoseCandidate } from '../services/talentApi';
import { recommendJobs } from '../services/fusionApi';
import { useCandidate } from '../contexts/CandidateContext';
import DiagnosisPage from './DiagnosisPage';
import RecommendationsPage from './RecommendationsPage';

beforeAll(() => {
  window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() });
  window.requestAnimationFrame = (cb) => cb();
});

const wrap = (ui) => <AntdApp><MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider></MemoryRouter></AntdApp>;

const diagnosis = {
  source: 'live', generatedAt: '2026-09-02', profile: { name: '候选人', experience: '三年开发经验', confidence: 88, skills: ['Python', 'SQL'] },
  matches: [
    { id: 'j1', role: '后端开发工程师', family: '软件工程', version: 'v2', score: 86, reason: '技能匹配', gaps: [{ skill: 'Agent 工作流', priority: 'high', current: 40, target: 80, reason: '缺少项目证据' }] },
    { id: 'j2', role: '数据工程师', family: '数据智能', version: 'v2', score: 72, reason: '部分匹配', gaps: [{ skill: '模型评测', priority: 'medium', current: 50, target: 70, reason: '需要补充' }] },
  ],
  gaps: [{ skill: 'Agent 工作流', priority: 'high', current: 40, target: 80, reason: '缺少项目证据' }],
  pipeline: { mode: 'full', capabilities: ['BM25 召回'] },
};

afterEach(() => { jest.clearAllMocks(); localStorage.clear(); });

describe('diagnosis flow', () => {
  it('loads sample diagnosis, switches role/gap and creates learning target', async () => {
    diagnoseCandidate.mockResolvedValue(diagnosis);
    const { container } = render(wrap(<DiagnosisPage />));
    expect(screen.getByText('上传一份简历，建立能力画像')).toBeTruthy();
    fireEvent.click(screen.getByText('陈同学-前端与AI项目简历.pdf'));
    await waitFor(() => expect(diagnoseCandidate).toHaveBeenCalled());
    await waitFor(() => expect(screen.getAllByText('后端开发工程师').length).toBeGreaterThan(0));
    fireEvent.click(screen.getByText('数据工程师'));
    expect(screen.getByText('模型评测')).toBeTruthy();
    fireEvent.click(screen.getByText('生成学习路径'));
    expect(JSON.parse(localStorage.getItem('careerTarget')).role).toBe('数据工程师');
    expect(container.querySelector('.diagnosis-results')).toBeTruthy();
  });

  it('shows validation and backend errors for invalid resume', async () => {
    diagnoseCandidate.mockRejectedValue(new Error('service unavailable'));
    render(wrap(<DiagnosisPage />));
    const upload = screen.getByText('选择文件');
    expect(upload).toBeTruthy();
    fireEvent.click(screen.getByText('陈同学-前端与AI项目简历.pdf'));
    await waitFor(() => expect(screen.getByText('service unavailable')).toBeTruthy());
  });
});

describe('recommendations flow', () => {
  it('loads sample candidate and renders fusion recommendations', async () => {
    const updateCandidateProfile = jest.fn();
    useCandidate.mockReturnValue({ candidateProfile: null, updateCandidateProfile, updateResumeFile: jest.fn() });
    recommendJobs.mockResolvedValue({ results: [{ job_id: 'j1', final_score: 0.88, score_breakdown: {}, meta: { title: '后端开发工程师' }, explanation: { reason: '匹配' } }] });
    const { rerender } = render(wrap(<RecommendationsPage />));
    fireEvent.click(screen.getByText('使用示例候选人（大模型算法工程师）'));
    expect(updateCandidateProfile).toHaveBeenCalled();
    const profile = updateCandidateProfile.mock.calls[0][0];
    useCandidate.mockReturnValue({ candidateProfile: profile, updateCandidateProfile, updateResumeFile: jest.fn() });
    rerender(wrap(<RecommendationsPage />));
    await waitFor(() => expect(screen.getByText(/找到 1 个推荐岗位/)).toBeTruthy());
  });

  it('renders empty recommendation state for an existing profile', async () => {
    useCandidate.mockReturnValue({ candidateProfile: { candidate: { id: 'c1', name: '候选人', skills: [] } }, updateCandidateProfile: jest.fn(), updateResumeFile: jest.fn() });
    recommendJobs.mockResolvedValue({ results: [] });
    render(wrap(<RecommendationsPage />));
    await waitFor(() => expect(screen.getByText('暂无匹配岗位')).toBeTruthy());
  });
});
