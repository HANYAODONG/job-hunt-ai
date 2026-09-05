import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App as AntdApp } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import RoleEvolutionCenterPage from './RoleEvolutionCenterPage';
import { getRoleEvolutionWorkspace } from '../services/talentApi';

jest.mock('../services/talentApi', () => ({
  getDiscoveryBatch: jest.fn(),
  deleteImportedMonth: jest.fn(),
  getRoleAnalytics: jest.fn(),
  getRoleEvolutionWorkspace: jest.fn(),
  importMonthlyJds: jest.fn(),
  reviewDiscoveryCandidate: jest.fn(),
  reviewPendingJob: jest.fn(),
  runSyntheticNewRoleFixture: jest.fn(),
  saveRoleOptimization: jest.fn(),
  submitRoleJd: jest.fn(),
}));

const workspace = {
  jobs: [{ name: '大模型应用工程师', summary: '岗位摘要', requiredSkills: [{ name: 'RAG' }] }],
  pending: [{ id: 'CHG-1' }],
  latest: {
    id: 'EV-1', role: '大模型应用工程师', version: 'v1.2', status: '待审核', summary: '岗位能力发生变化。',
    added: ['Agent 工作流'], removed: [], modified: ['RAG 优化'], evidence: 12, updatedAt: '2026-08-01',
  },
  analytics: {
    role: '大模型应用工程师', versions: [], trend: [], lifecycle: [], migration: [],
  },
  optimization: { name: '大模型应用工程师', requiredSkills: [{ name: 'RAG' }] },
};

describe('RoleEvolutionCenterPage', () => {
  const renderPage = () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><AntdApp><RoleEvolutionCenterPage /></AntdApp></MemoryRouter>
      </QueryClientProvider>,
    );
  };

  beforeEach(() => {
    getRoleEvolutionWorkspace.mockResolvedValue(workspace);
    require('../services/talentApi').getDiscoveryBatch.mockResolvedValue({ candidates: [], available_months: [], trigger_threshold: 10 });
    require('../services/talentApi').getRoleAnalytics.mockResolvedValue({ profileCompare: { summary: {}, from_profile: [], to_profile: [] } });
    require('../services/talentApi').runSyntheticNewRoleFixture.mockResolvedValue({
      synthetic_only: true, production_state_changed: false, fixture_jd_count: 12,
      route_statuses: ['potential_new_job'],
      result_summary: { title: '边缘智能体编排工程师', supporting_jd_count: 12, threshold: 10, threshold_met: true, status: '待人工审核' },
    });
  });

  it('shows the four core role-evolution views', async () => {
    renderPage();

    expect(await screen.findByText('岗位演化中心')).toBeTruthy();
    expect(screen.getByRole('button', { name: /单条 JD 更新/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /实时岗位演化/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /时序分析/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /人工优化/ })).toBeTruthy();
  });

  it('switches from JD input to the analytics view without losing context', async () => {
    renderPage();
    await screen.findByText('提交一条岗位 JD');

    fireEvent.click(screen.getByRole('button', { name: /时序分析/ }));

    await waitFor(() => expect(screen.getByText('岗位技能时序分析')).toBeTruthy());
    expect(screen.getAllByText('大模型应用工程师').length).toBeGreaterThan(0);
  });

  it('shows confirmed profile changes instead of a pending routing candidate', async () => {
    getRoleEvolutionWorkspace.mockResolvedValue({
      ...workspace,
      latest: {
        ...workspace.latest,
        role: 'AI Infra 工程师',
        status: '已生效',
        version: '2026-07',
        evidence: 19,
        added: ['Agent', 'Docker'],
        modified: ['Go ↑', 'CUDA ↓'],
        raw: { signal_skills: ['Agent', 'Docker'] },
        input: { month: '2026-07', job_title: 'AI Infra 工程师' },
        updatedAt: '2026-08-12T16:56:11.691156+00:00',
      },
    });
    renderPage();
    await screen.findByText('岗位演化中心');
    fireEvent.click(screen.getByRole('button', { name: /实时岗位演化/ }));

    expect(await screen.findByText(/AI Infra 工程师 · 本次岗位演化/)).toBeTruthy();
    expect(screen.getAllByText('已生效').length).toBeGreaterThan(0);
    expect(screen.getByText('2026-08-13 00:56')).toBeTruthy();
    expect(screen.queryByText('变化版本')).toBeNull();
    fireEvent.click(screen.getByRole('tab', { name: /记录/ }));
    expect(screen.getByText('岗位画像变化已记录')).toBeTruthy();
    expect(screen.queryByText('等待人工确认发布')).toBeNull();
  });

  it('shows a real monthly snapshot even when no new-role candidate is pending', async () => {
    const discoveryMock = require('../services/talentApi').getDiscoveryBatch;
    discoveryMock.mockReset();
    discoveryMock.mockResolvedValue({
      month: '2026-07', available_months: ['2026-06', '2026-07'], input_jd_count: 1541,
      deduplicated_jd_count: 1541, classified_jd_count: 1541, unmapped_jd_count: 0,
      role_count: 73, role_distribution: [{ standard_job: '大模型应用工程师', jd_count: 23 }],
      sample_jds: [{ job_id: 'GEN000401', job_title: '大模型应用算法岗位', standard_job: '大模型应用工程师', month: '2026-07' }],
      batch_status: '已完成归类', candidates: [], cluster_count: 0, trigger_threshold: 10,
      threshold_rule: '去重后的同类 JD 数量 > 10', guardrails: [],
    });
    renderPage();
    await screen.findByText('岗位演化中心');
    fireEvent.click(screen.getByRole('button', { name: /批量新岗位发现/ }));

    expect(await screen.findByText('当月标准岗位分布')).toBeTruthy();
    await waitFor(() => expect(discoveryMock).toHaveBeenCalled());
    expect(screen.getByText('已归类 JD')).toBeTruthy();
    expect(screen.queryByText('当月真实 JD 样例')).toBeNull();
    expect(screen.getByText(/已完成 1541 条 JD 的标准岗位归类/)).toBeTruthy();
  });

  it('runs the isolated new-role validation without claiming a production change', async () => {
    renderPage();
    await screen.findByText('岗位演化中心');
    fireEvent.click(screen.getByRole('button', { name: /批量新岗位发现/ }));
    await screen.findByText('月度新岗位发现闭环');
    fireEvent.click(screen.getByRole('button', { name: /验证新岗位发现/ }));

    expect(await screen.findByText('新岗位发现验证结果')).toBeTruthy();
    expect(screen.getByText('边缘智能体编排工程师')).toBeTruthy();
    expect(screen.getByText('正式池变更')).toBeTruthy();
  });

  it('shows only review records from the selected discovery month', async () => {
    const api = require('../services/talentApi');
    getRoleEvolutionWorkspace.mockResolvedValue({
      ...workspace,
      pending: [
        { item_id: 'aug-review', review_type: 'job', input: { month: '2026-08', job_title: '八月候选岗位' }, result: { route: { status: 'potential_new_job' } } },
        { item_id: 'jul-review', review_type: 'job', input: { month: '2026-07', job_title: '七月历史岗位' }, result: { route: { status: 'potential_new_job' } } },
      ],
    });
    api.getDiscoveryBatch.mockResolvedValue({
      month: '2026-08', available_months: ['2026-07', '2026-08'], candidates: [], trigger_threshold: 10,
    });
    renderPage();
    await screen.findByText('岗位演化中心');
    fireEvent.click(screen.getByRole('button', { name: /批量新岗位发现/ }));

    expect(await screen.findByText('八月候选岗位')).toBeTruthy();
    expect(screen.queryByText('七月历史岗位')).toBeNull();
    expect(screen.getByText('1 条待处理')).toBeTruthy();
  });

  it('clears only the selected monthly import after an explicit confirmation', async () => {
    const api = require('../services/talentApi');
    api.getDiscoveryBatch.mockResolvedValue({
      month: '2026-08', available_months: ['2026-08'], candidates: [], trigger_threshold: 10,
    });
    api.deleteImportedMonth.mockResolvedValue({ deleted_review_items: 12, production_state_changed: false });
    renderPage();
    await screen.findByText('岗位演化中心');
    fireEvent.click(screen.getByRole('button', { name: /批量新岗位发现/ }));
    const clearButton = await screen.findByRole('button', { name: /删除当前月数据/ });
    await waitFor(() => expect(clearButton.disabled).toBe(false));
    fireEvent.click(clearButton);
    fireEvent.click(await screen.findByRole('button', { name: '删除数据' }));
    await waitFor(() => expect(api.deleteImportedMonth).toHaveBeenCalledWith('2026-08'));
  });

});
