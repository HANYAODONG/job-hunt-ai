import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';

jest.mock('../services/api', () => ({ getJobById: jest.fn(), getSimilarJobs: jest.fn() }));
jest.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: () => false }) }));
jest.mock('../components/JobApplicationModal', () => () => null);
import { getJobById, getSimilarJobs } from '../services/api';
import JobDetailsPage from './JobDetailsPage';

const job = {
  id: 'j1', title: '后端开发工程师', company_name: '示例科技', location: { city: '合肥', state: '安徽', country: '中国' },
  remote_allowed: true, visa_sponsorship: false, job_type: 'full_time', experience_level: 'mid', salary: { min_salary: 180000, max_salary: 260000 },
  posted_date: '2026-09-01', application_deadline: '2026-10-01', description: '负责高并发服务开发。', responsibilities: ['建设服务'], required_skills: ['Java', 'Spring'], preferred_skills: ['Kubernetes'], benefits: [{ name: '五险一金', description: '标准配置' }],
};
const wrap = (ui) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/job/j1']}><Routes><Route path="/job/:jobId" element={ui} /></Routes></MemoryRouter></QueryClientProvider>;
beforeAll(() => { window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() }); });
beforeEach(() => { getJobById.mockResolvedValue(job); getSimilarJobs.mockResolvedValue([{ ...job, id: 'j2', title: 'Java 工程师' }]); });
afterEach(() => jest.clearAllMocks());

it('loads job details and related jobs through the canonical job API', async () => {
  render(wrap(<JobDetailsPage />));
  await waitFor(() => expect(screen.getByRole('heading', { name: '后端开发工程师' })).toBeTruthy());
  expect(screen.getByText('Java')).toBeTruthy();
  expect(screen.getByText('Java 工程师')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Apply Now' }));
  expect(getJobById).toHaveBeenCalledWith('j1');
  expect(getSimilarJobs).toHaveBeenCalledWith('j1', 5);
});
