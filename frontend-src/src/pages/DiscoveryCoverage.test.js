import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App as AntdApp } from 'antd';

jest.mock('../services/talentApi', () => ({
  getDiscoveryCandidates: jest.fn(), getMarketChangeCandidates: jest.fn(), getMarketRuntimeStatus: jest.fn(),
  getLiveMarketTrend: jest.fn(), importMarketCsv: jest.fn(), reviewDiscoveryCandidate: jest.fn(),
}));
jest.mock('../components/workbench/TechnicalInspector', () => () => <aside>证据检查器</aside>);

import { getDiscoveryCandidates, getLiveMarketTrend, getMarketChangeCandidates, getMarketRuntimeStatus, reviewDiscoveryCandidate } from '../services/talentApi';
import DiscoveryPage from './DiscoveryPage';

const role = { id: 'NEW-01', name: 'AI 语料工程师', domain: '人工智能', status: '待审核', skills: ['SFT 数据构建', 'RLHF'], signals: ['多平台高频共现'], evidence: 8, confidence: 91, updatedAt: '2026-09-02' };
const change = { id: 'CHANGE-01', name: '大模型应用工程师', domain: '人工智能', status: '待审核', skills: ['Agent 工作流'], signals: ['岗位技能变化'], evidence: 6, confidence: 86, updatedAt: '2026-09-02', version: 'v2.1', added: ['Agent 工作流'], removed: [], modified: ['模型评测'] };

beforeAll(() => { window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() }); });
beforeEach(() => {
  getDiscoveryCandidates.mockResolvedValue([role]);
  getMarketChangeCandidates.mockResolvedValue([change]);
  getMarketRuntimeStatus.mockResolvedValue({ available: true, bm25: { document_count: 10964 } });
  getLiveMarketTrend.mockResolvedValue({ skill_demand: { 'SFT 数据构建': 16, 'Agent 工作流': 20 }, related_skills: { 'SFT 数据构建': ['数据清洗'], 'Agent 工作流': ['RAG'] } });
  reviewDiscoveryCandidate.mockResolvedValue({});
});
afterEach(() => jest.clearAllMocks());

it('reviews new-role signals and displays a role-change version diff', async () => {
  render(<AntdApp><DiscoveryPage /></AntdApp>);
  await waitFor(() => expect(screen.getByText('AI 语料工程师')).toBeTruthy());
  expect(screen.getByText('岗位索引 10964')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /审核并发布/ }));
  await waitFor(() => expect(reviewDiscoveryCandidate).toHaveBeenCalledWith('NEW-01', 'publish'));
  fireEvent.click(screen.getByRole('button', { name: /能力变化信号/ }));
  await waitFor(() => expect(screen.getByText('VERSION DIFF')).toBeTruthy());
  expect(screen.getAllByText('Agent 工作流').length).toBeGreaterThan(1);
});
