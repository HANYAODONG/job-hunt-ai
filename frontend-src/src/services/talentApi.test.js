import { getJobById, getJobRecommendations, uploadResume } from './api';
import { diagnoseCandidate, TALENT_API_CAPABILITIES } from './talentApi';

jest.mock('./api', () => ({
  getJobById: jest.fn(),
  getJobRecommendations: jest.fn(),
  uploadResume: jest.fn(),
}));

describe('diagnoseCandidate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.REACT_APP_USE_RESUME_MOCK;
  });

  it('keeps unsupported workbench contracts explicit', () => {
    expect(TALENT_API_CAPABILITIES).toMatchObject({
      resumeDiagnosis: 'live',
      recruitment: 'mock-only',
      candidatePipeline: 'mock-only',
    });
  });

  it('normalizes the real resume recommendation workflow for the diagnosis UI', async () => {
    const resume = new File(['resume'], 'resume.pdf', { type: 'application/pdf' });
    const candidate = {
      id: 'candidate-1',
      name: '测试用户',
      skills: [{ name: 'React' }],
      experience: [{ position: '前端工程师' }],
    };
    uploadResume.mockResolvedValue({
      candidate,
      extracted_skills: ['React', 'JavaScript'],
      experience_summary: '两年前端项目经验',
    });
    getJobRecommendations.mockResolvedValue([{
      job_id: 'job-1',
      match_score: 0.82,
      matching_skills: ['React'],
      missing_skills: ['TypeScript'],
      overall_fit: 'good',
    }]);
    getJobById.mockResolvedValue({
      id: 'job-1',
      title: '前端开发工程师',
      company_name: '示例企业',
      job_family: '软件工程',
      required_skills: ['React', 'TypeScript'],
    });

    const result = await diagnoseCandidate({ resumeFile: resume });

    expect(uploadResume).toHaveBeenCalledWith(resume);
    expect(getJobRecommendations).toHaveBeenCalledWith(candidate);
    expect(result.source).toBe('live');
    expect(result.profile).toMatchObject({ name: '测试用户', skills: ['React', 'JavaScript'] });
    expect(result.matches[0]).toMatchObject({
      id: 'job-1',
      role: '前端开发工程师',
      family: '软件工程',
      score: 82,
    });
    expect(result.matches[0].gaps[0]).toMatchObject({ skill: 'TypeScript', current: 0, target: 100 });
  });
});
