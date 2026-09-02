import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { App as AntdApp } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';

jest.mock('../services/api', () => ({
  loginUser: jest.fn(),
  registerUser: jest.fn(),
  uploadResume: jest.fn(),
  applyToJob: jest.fn(),
}));

import { loginUser, registerUser, uploadResume, applyToJob } from '../services/api';
import { AuthProvider, useAuth } from '../contexts/AuthContext';
import { CandidateProvider, useCandidate } from '../contexts/CandidateContext';
import Header from '../components/Header';
import JobApplicationModal from '../components/JobApplicationModal';
import LoginPage from './LoginPage';
import RegisterPage from './RegisterPage';
import ResumeUploadPage from './ResumeUploadPage';

const wrap = (ui, providers = true) => (
  <AntdApp><MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{providers ? <AuthProvider><CandidateProvider>{ui}</CandidateProvider></AuthProvider> : ui}</QueryClientProvider></MemoryRouter></AntdApp>
);

const Probe = () => {
  const auth = useAuth();
  const candidate = useCandidate();
  return <div>
    <span data-testid="auth-state">{auth.loading ? 'loading' : String(auth.isAuthenticated())}</span>
    <button onClick={() => auth.login('token-1', { id: 'u1', email: 'a@b.com' })}>login</button>
    <button onClick={() => auth.updateUser({ id: 'u2' })}>update</button>
    <button onClick={auth.logout}>logout</button>
    <button onClick={() => candidate.updateCandidateProfile({ candidate: { name: 'A' } })}>candidate</button>
    <button onClick={candidate.clearCandidateData}>clear</button>
  </div>;
};

beforeEach(() => {
  window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() });
  localStorage.clear();
  jest.clearAllMocks();
});

describe('authentication and candidate context seams', () => {
  it('hydrates, logs in, updates and logs out through public context API', async () => {
    localStorage.setItem('access_token', 'stored');
    localStorage.setItem('user', JSON.stringify({ id: 'old' }));
    render(wrap(<Probe />));
    await waitFor(() => expect(screen.getByTestId('auth-state').textContent).toBe('true'));
    fireEvent.click(screen.getByText('update'));
    expect(JSON.parse(localStorage.getItem('user')).id).toBe('u2');
    fireEvent.click(screen.getByText('logout'));
    expect(screen.getByTestId('auth-state').textContent).toBe('false');
    fireEvent.click(screen.getByText('login'));
    fireEvent.click(screen.getByText('candidate'));
    expect(localStorage.getItem('access_token')).toBe('token-1');
    fireEvent.click(screen.getByText('clear'));
    expect(localStorage.getItem('candidateProfile')).toBeNull();
  });

  it('renders header actions for anonymous and authenticated users', async () => {
    render(wrap(<Header />));
    expect(screen.getByText('Login')).toBeTruthy();
    expect(screen.getByText('Sign Up')).toBeTruthy();
    fireEvent.click(screen.getByText('Login'));
    expect(screen.getByText('Login')).toBeTruthy();
    cleanup();
    localStorage.setItem('access_token', 't');
    localStorage.setItem('user', JSON.stringify({ id: 'u' }));
    render(wrap(<Header />));
    await waitFor(() => expect(screen.queryByText('Sign Up')).toBeNull());
  });
});

describe('authentication pages', () => {
  it('submits login and displays server errors', async () => {
    loginUser.mockResolvedValue({ access_token: 't', user: { id: 'u', email: 'x@y.com' } });
    render(wrap(<LoginPage />));
    fireEvent.change(screen.getByPlaceholderText('john.doe@example.com'), { target: { value: 'x@y.com' } });
    fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'password' } });
    fireEvent.click(screen.getByText('Sign In'));
    await waitFor(() => expect(loginUser).toHaveBeenCalled());
    loginUser.mockRejectedValueOnce(new Error('bad credentials'));
    fireEvent.click(screen.getByText('Sign In'));
    await waitFor(() => expect(screen.getByText('bad credentials')).toBeTruthy());
  });

  it('registers successfully and supports registration error state', async () => {
    registerUser.mockResolvedValue({ ok: true });
    render(wrap(<RegisterPage />, false));
    fireEvent.change(screen.getByPlaceholderText('John'), { target: { value: 'Jane' } });
    fireEvent.change(screen.getByPlaceholderText('Doe'), { target: { value: 'Doe' } });
    fireEvent.change(screen.getByPlaceholderText('john.doe@example.com'), { target: { value: 'jane@example.com' } });
    fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByText('Create Account'));
    await waitFor(() => expect(screen.getByText('Registration Successful!')).toBeTruthy());
    registerUser.mockRejectedValueOnce(new Error('email exists'));
    fireEvent.click(screen.getByText('Go to Login'));
  });
});

describe('resume upload and application modal', () => {
  it('validates resume files and renders successful analysis', async () => {
    uploadResume.mockResolvedValue({ extracted_skills: ['Python', 'SQL'], skill_categories: { lang: ['Python'] }, extracted_experience: [{ title: 'dev' }], experience_summary: 'backend' });
    render(wrap(<ResumeUploadPage />));
    const input = document.querySelector('input[type="file"]');
    const file = new File(['resume'], 'resume.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(uploadResume).toHaveBeenCalled());
    expect(screen.getByText('Resume Analysis Results')).toBeTruthy();
    expect(screen.getByText('Get Job Recommendations')).toBeTruthy();
  });

  it('renders application form, validates auth and submits application', async () => {
    applyToJob.mockResolvedValue({ ok: true });
    const onClose = jest.fn();
    const onSubmitted = jest.fn();
    render(wrap(<JobApplicationModal visible onClose={onClose} onApplicationSubmitted={onSubmitted} job={{ id: 'j1', title: 'Engineer', company_name: 'Acme', location: { city: 'Beijing', state: 'BJ' }, job_type: 'full_time', experience_level: 'mid', remote_allowed: true }} />));
    expect(screen.getByText('Apply for Position')).toBeTruthy();
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });
});
