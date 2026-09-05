import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App as AntdApp } from 'antd';
import { MemoryRouter, Routes, Route, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';

jest.mock('../services/talentApi', () => ({
  getTalentOverview: jest.fn(),
  getEvaluationReport: jest.fn(),
  getDataGovernance: jest.fn(),
  getLearningPlan: jest.fn(),
  getRoleCatalog: jest.fn(),
  getCapabilityGraph: jest.fn(),
  getCapabilityRoleJobs: jest.fn(),
  diagnoseCandidate: jest.fn(),
}));

jest.mock('../components/workbench/GalaxyScene', () => ({ onNodeSelect }) => <div data-testid="galaxy-scene"><button onClick={() => onNodeSelect('d1')}>select-node</button>scene</div>);
jest.mock('../services/graphSync', () => ({ subscribeGraphDataChanged: jest.fn(() => jest.fn()) }));

import {
  getTalentOverview,
  getEvaluationReport,
  getDataGovernance,
  getLearningPlan,
  getRoleCatalog,
  getCapabilityGraph,
  getCapabilityRoleJobs,
} from '../services/talentApi';
import DashboardPage from './DashboardPage';
import EvaluationPage from './EvaluationPage';
import GovernancePage from './GovernancePage';
import LearningPlanPage from './LearningPlanPage';
import RoleLibraryPage from './RoleLibraryPage';
import GraphPage from './GraphPage';

beforeAll(() => {
  if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() });
  if (!Element.prototype.requestFullscreen) Element.prototype.requestFullscreen = jest.fn(() => Promise.resolve());
  if (!document.exitFullscreen) document.exitFullscreen = jest.fn(() => Promise.resolve());
  if (!global.ResizeObserver) global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
});

const wrap = (ui, query = false) => {
  const content = query
    ? <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>
    : ui;
  return <AntdApp><MemoryRouter>{content}</MemoryRouter></AntdApp>;
};

const enterpriseWrap = (ui) => <AntdApp><MemoryRouter><Routes><Route path="*" element={<Outlet context={{ workspaceRole: 'enterprise' }} />}><Route index element={ui} /></Route></Routes></MemoryRouter></AntdApp>;

const role = {
  id: 'r1', name: '后端开发工程师', family: '软件工程', level: '中级', domain: '软件工程',
  version: 'v2', status: '已发布', evidenceCount: 32, growth: '+12%', updatedAt: '2026-09-01',
  summary: '负责服务端系统设计、开发与稳定性建设。', responsibilities: ['设计服务接口', '保障系统稳定'],
  requiredSkills: [{ name: 'Python', trend: '+8%', level: 90 }, { name: 'SQL', trend: '+3%', level: 75 }],
  bonusSkills: ['Docker'], scenarios: ['云服务'], versions: [{ version: 'v2', date: '2026-09-01', note: '统一岗位定义' }],
};

afterEach(() => jest.clearAllMocks());

describe('workbench business pages', () => {
  it('renders candidate dashboard without loading backend data', () => {
    getTalentOverview.mockResolvedValue({ demandTrend: [], reviewTasks: [], sources: [] });
    render(wrap(<DashboardPage />));
    expect(screen.getByText('下一步，把能力差距变成可展示的作品')).toBeTruthy();
    expect(screen.getAllByText('大模型应用工程师').length).toBeGreaterThan(0);
    expect(screen.getByText('继续阶段 2')).toBeTruthy();
  });

  it('renders enterprise dashboard data and review queue', async () => {
    getTalentOverview.mockResolvedValue({
      demandTrend: [{ month: '2026-09', ai: 10, data: 8 }],
      reviewTasks: [{ id: 'q1', name: 'Agent 工作流', type: '岗位信号', updatedAt: '今天', confidence: 88 }],
      sources: [{ name: '招聘平台', freshness: '今天', coverage: 98 }],
    });
    render(enterpriseWrap(<DashboardPage />));
    await waitFor(() => expect(screen.getByText('今天，从 18 项市场信号开始')).toBeTruthy());
    expect(screen.getByText('Agent 工作流')).toBeTruthy();
    expect(screen.getByText('招聘平台')).toBeTruthy();
  });

  it('switches evaluation metrics and emits run/error actions', async () => {
    getEvaluationReport.mockResolvedValue({
      metrics: [
        { label: 'JD 解析准确率', value: 94, target: 90, tone: 'blue' },
        { label: '简历技能覆盖率', value: 82, target: 90, tone: 'amber' },
      ],
      errors: [{ category: '岗位边界', count: 2, example: '相近岗位误判' }],
    });
    render(wrap(<EvaluationPage />));
    await waitFor(() => expect(screen.getByText('评测中心')).toBeTruthy());
    expect(screen.getAllByText('JD 解析准确率').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('简历技能覆盖率'));
    expect(screen.getByText('NEEDS REVIEW')).toBeTruthy();
    fireEvent.click(screen.getByText('查看样本'));
    fireEvent.click(screen.getByText('运行评测'));
  });

  it('filters governance sources, selects a source and runs checks', async () => {
    getDataGovernance.mockResolvedValue({
      sources: [
        { key: 'a', source: '招聘平台', owner: '数据组', freshness: '今天', records: 100, valid: 98, duplicate: 2 },
        { key: 'b', source: '历史快照', owner: '平台组', freshness: '7 天前', records: 40, valid: 90, duplicate: 8 },
      ],
      issues: [{ title: '来源延迟', detail: '快照需要更新' }],
    });
    render(wrap(<GovernancePage />));
    await waitFor(() => expect(screen.getByText('数据治理')).toBeTruthy());
    expect(screen.getAllByText('招聘平台').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /需关注/ }));
    expect(screen.getByText('历史快照')).toBeTruthy();
    fireEvent.click(screen.getByText('运行校验'));
    fireEvent.click(screen.getByText('查看记录'));
  });

  it('renders learning plan and switches stage', async () => {
    getLearningPlan.mockResolvedValue({ profile: '候选人', targetRole: '后端开发工程师', targetVersion: 'v2', matchScore: 76, progress: 30, currentStage: '阶段 1', updatedAt: '今天', stages: [
      { id: 's1', phase: '阶段 1', duration: '1 周', title: '补齐 Python', skill: 'Python', status: '已完成', goal: '掌握基础', tasks: ['练习'], outcome: '项目' },
      { id: 's2', phase: '阶段 2', duration: '2 周', title: '补齐 Docker', skill: 'Docker', status: '进行中', goal: '完成部署', tasks: ['部署'], outcome: '镜像' },
    ] });
    render(wrap(<LearningPlanPage />));
    await waitFor(() => expect(screen.getByText('学习与改进计划')).toBeTruthy());
    expect(screen.getAllByText('补齐 Docker').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('补齐 Python'));
    expect(screen.getByText('掌握基础')).toBeTruthy();
    fireEvent.click(screen.getByText('更新进度'));
  });

  it('does not crash when the learning plan has no stages', async () => {
    getLearningPlan.mockResolvedValue({
      profile: '候选人', targetRole: '后端开发工程师', targetVersion: 'v2', stages: [],
    });
    render(wrap(<LearningPlanPage />));
    await waitFor(() => expect(screen.getByText('暂无可生成的学习阶段')).toBeTruthy());
    expect(screen.getByText('重新诊断')).toBeTruthy();
  });

  it('loads role catalog, searches by skill and navigates', async () => {
    getRoleCatalog.mockResolvedValue([role, { ...role, id: 'r2', name: '数据工程师', requiredSkills: [{ name: 'Spark', trend: '0%', level: 70 }, { name: 'SQL', trend: '0%', level: 60 }] }]);
    render(wrap(<RoleLibraryPage />));
    await waitFor(() => expect(screen.getAllByText('后端开发工程师').length).toBeGreaterThan(0));
    fireEvent.change(screen.getByPlaceholderText('搜索岗位或技能'), { target: { value: 'Spark' } });
    expect(screen.getByText('数据工程师')).toBeTruthy();
    fireEvent.click(screen.getByText('数据工程师'));
    expect(screen.getByText('负责服务端系统设计、开发与稳定性建设。')).toBeTruthy();
  });

  it('renders graph, changes level/year and navigates to a role', async () => {
    const tree = { id: 'root', type: 'root', label: '岗位宇宙', children: [{ id: 'd1', type: 'domain', label: '人工智能', detail: 'AI', count: 2, growth: '+1%', children: [{ id: 'f1', type: 'family', label: '算法', detail: '方向', count: 1, growth: '+2%', children: [{ id: 'r1', type: 'role', label: '算法工程师', detail: '岗位', count: 1, growth: '+3%', standard_category: '人工智能', standard_direction: '算法', standard_role: '算法工程师', skills: ['Python'] }] }] }] };
    getCapabilityGraph.mockResolvedValue({ tree, stacks: ['Python'], summary: { domains: 1, families: 1, roles: 1, skills: 2, relationships: 3, needs_review: 0, single_role_families: 0 } });
    getCapabilityRoleJobs.mockResolvedValue({ total: 1, items: [{ id: 'j1', title: '算法工程师 JD', location: '北京', summary: '模型开发', responsibilities: ['训练'], requiredSkills: [{ name: 'Python' }] }] });
    render(wrap(<GraphPage />, true));
    await waitFor(() => expect(screen.getByText('新一代信息技术岗位银河')).toBeTruthy());
    fireEvent.click(screen.getByText('2025'));
    fireEvent.click(screen.getByRole('button', { name: 'select-node' }));
    await waitFor(() => expect(screen.getAllByText('人工智能').length).toBeGreaterThan(0));
    expect(screen.getByTestId('galaxy-scene')).toBeTruthy();
  });
});
