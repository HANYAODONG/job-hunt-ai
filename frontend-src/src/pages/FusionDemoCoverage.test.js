import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App as AntdApp } from 'antd';

jest.mock('../services/fusionApi', () => ({
  getMockRankedResults: jest.fn(),
  recommendJobs: jest.fn(),
  getLayeredWeights: jest.fn(),
  updateLayeredWeights: jest.fn(),
  resetWeights: jest.fn(),
  loadFusionResults: jest.fn(),
}));
jest.mock('../components/FusionScoreCard', () => () => <div>融合结果卡片</div>);

import { getLayeredWeights, recommendJobs } from '../services/fusionApi';
import FusionDemoPage from './FusionDemoPage';

beforeAll(() => {
  window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() });
  window.HTMLElement.prototype.scrollIntoView = jest.fn();
});

beforeEach(() => {
  getLayeredWeights.mockResolvedValue({ weights: {
    relevance_bm25: 0.4, relevance_semantic: 0.6, ability_skill: 0.7, ability_graph: 0.3,
    relevance_base: 0.7, ability_multiplier: 0.3, family_discount: 1,
  } });
  recommendJobs.mockResolvedValue({ query_id: 'resume-1', results: [], weights_used: {} });
});

afterEach(() => jest.clearAllMocks());

it('renders the unified recommendation entry point and loads layered weights', async () => {
  render(<AntdApp><FusionDemoPage /></AntdApp>);
  expect(screen.getByText('统一推荐接口模式')).toBeTruthy();
  expect(screen.getByText('分层融合权重')).toBeTruthy();
  await waitFor(() => expect(getLayeredWeights).toHaveBeenCalled());
  expect(screen.getByText('尚未生成融合结果')).toBeTruthy();
});
