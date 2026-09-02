import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from 'react-query';

jest.mock('../services/api', () => ({ getPersonalizedRecommendations: jest.fn(), getRerankingExplanation: jest.fn() }));
jest.mock('../components/RerankingScore', () => () => <div>匹配得分解释</div>);
import PersonalizedRecommendationsPage from './PersonalizedRecommendationsPage';

beforeAll(() => { window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() }); });

it('renders the personalised recommendation form in its safe initial state', () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PersonalizedRecommendationsPage /></QueryClientProvider>);
  expect(screen.getByRole('heading', { name: /Personalized Job Recommendations/ })).toBeTruthy();
  expect(screen.getByText('Choose Resume File')).toBeTruthy();
  expect(screen.getByText('Get Recommendations')).toBeTruthy();
});
