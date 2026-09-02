import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';

jest.mock('../services/api', () => ({
  searchJobs: jest.fn(),
  searchJobsWithResume: jest.fn(),
  extractKeywords: jest.fn(),
  rerankWithKeywords: jest.fn(),
  getRerankingExplanation: jest.fn(),
}));
jest.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: () => false, user: null }) }));
jest.mock('../components/JobApplicationModal', () => () => null);
jest.mock('../components/RerankingScore', () => () => <div>重排分数</div>);

import { extractKeywords, searchJobs } from '../services/api';
import SearchPage from './SearchPage';

const wrap = (ui) => <MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider></MemoryRouter>;

beforeAll(() => {
  window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() });
});

beforeEach(() => {
  searchJobs.mockResolvedValue({ total: 0, jobs: [] });
  extractKeywords.mockResolvedValue({ job_titles: ['后端开发工程师'], skills: ['Python'], salary: null, locations: [] });
});

afterEach(() => jest.clearAllMocks());

it('submits an example query through the normal search and keyword extraction workflow', async () => {
  render(wrap(<SearchPage />));
  fireEvent.click(screen.getByText('Looking for a backend developer role using Python, Django, and PostgreSQL with experience in microservices architecture'));
  await waitFor(() => expect(searchJobs).toHaveBeenCalledWith(expect.objectContaining({
    query: expect.stringContaining('backend developer'), page: 1, page_size: 20,
  })));
  await waitFor(() => expect(extractKeywords).toHaveBeenCalledWith(expect.stringContaining('backend developer')));
});
