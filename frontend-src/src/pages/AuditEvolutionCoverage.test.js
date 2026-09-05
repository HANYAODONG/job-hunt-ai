import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App as AntdApp } from 'antd';
import { MemoryRouter } from 'react-router-dom';

jest.mock('../services/talentApi', () => ({ getJdQualitySample: jest.fn(), getRoleEvolution: jest.fn() }));
import { getJdQualitySample, getRoleEvolution } from '../services/talentApi';
import JdQualityPage from './JdQualityPage';
import EvolutionPage from './EvolutionPage';

beforeAll(() => { window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() }); });
const wrap = (ui) => <AntdApp><MemoryRouter>{ui}</MemoryRouter></AntdApp>;

describe('JD quality audit and role evolution', () => {
  it('filters audit samples by risk and loads the next batch', async () => {
    getJdQualitySample.mockResolvedValue({ items: [
      { job_id: 'j1', title: '后端岗位', risk_level: 'high', inflation_score: .8, noise_score: .2, evidence_risk: .4, local_summary: '需复核', evidence: ['技能堆叠'], graph_policy: 'hold_for_review', suspected_inflated_skills: ['Python'] },
      { job_id: 'j2', title: '数据岗位', risk_level: 'low', inflation_score: .1, noise_score: .1, evidence_risk: .1, local_summary: '可信', evidence: [], graph_policy: 'allow_with_trace' },
    ], summary: { total: 2, risk_counts: { high: 1, medium: 0, low: 1 }, average_inflation_score: .45, top_issues: [{ issue: '技能堆叠', count: 1 }], top_suspected_skills: [{ skill: 'Python', count: 1 }] } });
    render(wrap(<JdQualityPage />));
    await waitFor(() => expect(screen.getByText('JD 通胀与噪声检测')).toBeTruthy());
    expect(screen.getByText('后端岗位')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /高风险 1/ }));
    expect(screen.queryByText('数据岗位')).toBeNull();
    fireEvent.click(screen.getByText('换一批'));
    await waitFor(() => expect(getJdQualitySample).toHaveBeenCalledWith(expect.objectContaining({ offset: 30, useLlm: false })));
    await waitFor(() => expect(screen.getByText(/第 31-32 条/)).toBeTruthy());
  });

  it('switches role versions and opens evidence drawer', async () => {
    getRoleEvolution.mockResolvedValue({ role: '大模型应用工程师', versions: [
      { version: 'v2', date: '2026-09-01', status: '当前版本', summary: '新增 Agent 能力', added: ['Agent'], removed: [], modified: [], evidence: 3 },
      { version: 'v1', date: '2026-01-01', status: '历史版本', summary: '基础版本', added: [], removed: ['旧技能'], modified: [], evidence: 1 },
    ] });
    render(wrap(<EvolutionPage />));
    await waitFor(() => expect(screen.getByText('岗位演化分析')).toBeTruthy());
    expect(screen.getByText('新增 Agent 能力')).toBeTruthy();
    fireEvent.click(screen.getByText('v1'));
    expect(screen.getByText('基础版本')).toBeTruthy();
    fireEvent.click(screen.getByText('查看'));
    expect(screen.getByText('变更证据')).toBeTruthy();
  });
});
