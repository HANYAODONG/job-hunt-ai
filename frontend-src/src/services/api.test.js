import { createResumeSearchForm } from './api';

jest.mock('axios', () => ({
  create: () => ({
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  }),
}));

describe('createResumeSearchForm', () => {
  it('uses the backend multipart field contract', () => {
    const resume = new File(['resume'], 'resume.pdf', { type: 'application/pdf' });
    const form = createResumeSearchForm({
      query: 'React 前端工程师',
      location: '合肥',
      remote_allowed: false,
      required_skills: ['React', 'TypeScript'],
      preferred_skills: ['Three.js'],
      limit: 8,
    }, resume);

    expect(form.get('resume_file')).toBe(resume);
    expect(form.get('query')).toBe('React 前端工程师');
    expect(form.get('location')).toBe('合肥');
    expect(form.get('remote_allowed')).toBe('false');
    expect(form.getAll('required_skills')).toEqual(['React', 'TypeScript']);
    expect(form.getAll('preferred_skills')).toEqual(['Three.js']);
    expect(form.get('limit')).toBe('8');
  });
});
