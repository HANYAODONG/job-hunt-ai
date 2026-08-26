import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App as AntdApp } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import RoleEvolutionCenterPage from './RoleEvolutionCenterPage';
import { getRoleEvolutionWorkspace } from '../services/talentApi';

jest.mock('../services/talentApi', () => ({
  getRoleEvolutionWorkspace: jest.fn(),
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
});
