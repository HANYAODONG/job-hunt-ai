import { getJobById, getJobRecommendations, uploadResume } from './api';
import {
  analyzeKnowledgeGraphGap,
  rerankSemantic,
  searchBm25,
} from './intelligenceApi';
import { rankJobs } from './fusionApi';
import { diagnoseCandidate, TALENT_API_CAPABILITIES } from './talentApi';

jest.mock('./api', () => ({
  getJobById: jest.fn(),
  getJobRecommendations: jest.fn(),
  uploadResume: jest.fn(),
}));

jest.mock('./intelligenceApi', () => ({
  analyzeKnowledgeGraphGap: jest.fn(),
  getMarketRuntime: jest.fn(),
  ingestMarketCsv: jest.fn(),
  rerankSemantic: jest.fn(),
  searchBm25: jest.fn(),
}));

jest.mock('./fusionApi', () => ({
  rankJobs: jest.fn(),
}));

describe('diagnoseCandidate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.REACT_APP_USE_RESUME_MOCK;
  });

  it('keeps unsupported workbench contracts explicit', () => {
    expect(TALENT_API_CAPABILITIES).toMatchObject({
      resumeDiagnosis: 'live',
      fusionRanking: 'live',
      marketSignals: 'partial-live',
      recruitment: 'mock-only',
      candidatePipeline: 'mock-only',
    });
  });

  it('runs and normalizes the complete intelligence pipeline', async () => {
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
    searchBm25.mockResolvedValue({ hits: [{
      job_id: 'job-1',
      score: 12,
      title: '高级前端开发工程师',
      standard_job: '前端开发工程师',
      company: '示例企业',
      job_family: '软件工程',
      skills: ['React', 'TypeScript'],
      description: '负责 Web 应用开发',
    }] });
    rerankSemantic.mockResolvedValue({
      candidates: [{ job_id: 'job-1', semantic_score: 0.86, semantic_rank: 1 }],
    });
    analyzeKnowledgeGraphGap.mockResolvedValue({
      job_id: 'job-1',
      job_required_skills: ['React', 'TypeScript'],
      matched_skills: ['React'],
      missing_skills: ['TypeScript'],
      skill_coverage: 0.5,
      job_family_match: 1,
      graph_relatedness: 0.4,
      evidence_paths: ['Candidate -> HAS_SKILL -> React <- REQUIRES_SKILL <- Job'],
    });
    rankJobs.mockResolvedValue({
      results: [{
        job_id: 'job-1',
        final_score: 0.78,
        rank: 1,
        score_breakdown: { bm25: 1, semantic: 0.86, skill_coverage: 0.5, job_family: 1, graph: 0.4 },
        explanation: '语义与岗位族匹配较好',
        missing_skills: ['TypeScript'],
        evidence_paths: ['Candidate -> HAS_SKILL -> React <- REQUIRES_SKILL <- Job'],
      }],
    });

    const result = await diagnoseCandidate({ resumeFile: resume });

    expect(searchBm25).toHaveBeenCalledWith(expect.stringContaining('React'), { size: 8 });
    expect(rankJobs).toHaveBeenCalledWith('candidate-1', [expect.objectContaining({
      job_id: 'job-1',
      bm25_score: 1,
      semantic_score: 0.86,
      skill_coverage: 0.5,
    })]);
    expect(getJobRecommendations).not.toHaveBeenCalled();
    expect(result.pipeline).toMatchObject({ mode: 'full', warning: null });
    expect(result.matches[0]).toMatchObject({
      id: 'job-1',
      role: '前端开发工程师',
      family: '软件工程',
      score: 78,
      evidencePaths: ['Candidate -> HAS_SKILL -> React <- REQUIRES_SKILL <- Job'],
    });
    expect(result.matches[0].gaps[0]).toMatchObject({ skill: 'TypeScript', current: 0, target: 100 });
  });

  it('falls back to the existing recommendation workflow when canonical indexes cannot form a full chain', async () => {
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
    searchBm25.mockRejectedValue(new Error('BM25 索引不可用'));
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
    expect(result.pipeline).toMatchObject({ mode: 'legacy-fallback', warning: 'BM25 索引不可用' });
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
