import { getJobById, getJobRecommendations, searchJobsWithResume, uploadResume } from './api';
import {
  analyzeKnowledgeGraphGap,
  rerankSemantic,
  searchBm25,
} from './intelligenceApi';
import { rankJobs } from './fusionApi';
import {
  diagnoseCandidate,
  getRoleEvolutionWorkspace,
  saveRoleOptimization,
  submitRoleJd,
  TALENT_API_CAPABILITIES,
} from './talentApi';

jest.mock('./api', () => ({
  getJobById: jest.fn(),
  getJobRecommendations: jest.fn(),
  searchJobsWithResume: jest.fn(),
  uploadResume: jest.fn(),
}));

jest.mock('./intelligenceApi', () => ({
  analyzeKnowledgeGraphGap: jest.fn(),
  getMarketRuntime: jest.fn(),
  getTalentCandidates: jest.fn(),
  getTalentCandidateExplanation: jest.fn(),
  getTalentJobs: jest.fn(),
  getTalentMarketStats: jest.fn(),
  ingestMarketCsv: jest.fn(),
  patchTalentCandidateStage: jest.fn(),
  putTalentJob: jest.fn(),
  rankRoleAware: jest.fn(),
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

  it('reports the live and fallback boundaries of workbench contracts', () => {
    expect(TALENT_API_CAPABILITIES).toMatchObject({
      resumeDiagnosis: 'live',
      fusionRanking: 'live',
      marketSignals: 'partial-live',
      recruitment: 'live-with-fallback',
      candidatePipeline: 'live-with-fallback',
    });
  });

  it('exposes the four role-evolution workspaces with stable fallback data', async () => {
    const result = await getRoleEvolutionWorkspace();

    expect(result).toEqual(expect.objectContaining({
      jobs: expect.any(Array),
      pending: expect.any(Array),
      latest: expect.objectContaining({ role: expect.any(String), added: expect.any(Array) }),
      analytics: expect.objectContaining({ versions: expect.any(Array), trend: expect.any(Array) }),
      optimization: expect.objectContaining({ name: expect.any(String) }),
    }));
  });

  it('uses a real job for role-evolution analytics instead of the backend default', async () => {
    const previousApiUrl = process.env.REACT_APP_API_URL;
    const previousFetch = global.fetch;
    process.env.REACT_APP_API_URL = 'http://role-evolution.test/api/v1';
    const payloads = {
      '/jd-update/analytics/overview': {},
      '/jd-update/analytics/jobs': ['大模型应用工程师'],
      '/jd-update/reviews': [],
      '/jd-update/optimization/profile': { skills: [] },
      '/jd-update/analytics/job-trend': {
        standard_job: '大模型应用工程师',
        months: ['2026-07'],
        series: [{ points: [{ frequency: 0.8 }] }],
      },
      '/jd-update/analytics/lifecycle': {
        rows: [
          { skill: '旧技能', lifecycle_status: '废弃技能', current_monthly_skill_frequency: 0 },
          { skill: '核心技能', lifecycle_status: '稳定核心技能', current_monthly_skill_frequency: 0.8 },
        ],
      },
      '/jd-update/analytics/skill-migration': { spread: [] },
    };
    global.fetch = jest.fn(async (url) => {
      const key = Object.keys(payloads).find((path) => url.includes(path));
      return { ok: true, json: async () => payloads[key] || {} };
    });

    jest.resetModules();
    const { getRoleEvolutionWorkspace: getLiveWorkspace } = require('./talentApi');
    const result = await getLiveWorkspace();

    expect(result.analytics.role).toBe('大模型应用工程师');
    expect(result.analytics.lifecycle[0]).toMatchObject({ skill: '核心技能', frequency: 0.8 });
    expect(global.fetch.mock.calls.some(([url]) => url.includes('analytics/job-trend') && url.includes('standard_job=%E5%A4%A7%E6%A8%A1%E5%9E%8B%E5%BA%94%E7%94%A8%E5%B7%A5%E7%A8%8B%E5%B8%88'))).toBe(true);

    global.fetch = previousFetch;
    if (previousApiUrl === undefined) delete process.env.REACT_APP_API_URL;
    else process.env.REACT_APP_API_URL = previousApiUrl;
  });

  it('keeps JD update and optimization payloads usable when the service is offline', async () => {
    const submitted = await submitRoleJd({ job_title: '测试岗位', month: '2026-08' });
    const saved = await saveRoleOptimization({ standard_job: '大模型应用工程师', changes: [] });

    expect(submitted).toMatchObject({ effectId: expect.any(String), status: expect.any(String) });
    expect(saved).toMatchObject({ status: '已保存', standard_job: '大模型应用工程师' });
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

    expect(searchBm25).toHaveBeenCalledWith(expect.stringContaining('React'), { size: 100 });
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

  it('uses the local canonical two-stage result for uploaded resume diagnosis', async () => {
    const resume = new File(['resume'], 'resume.pdf', { type: 'application/pdf' });
    uploadResume.mockResolvedValue({
      candidate: { id: 'candidate-2', name: '本地测试用户', skills: [] },
      extracted_skills: ['Python'],
      experience_summary: '后端项目经验',
    });
    searchJobsWithResume.mockResolvedValue({
      explanations: {
        matching_pipeline: 'canonical_two_stage_v2',
        selected_canonical_role: '后端开发工程师',
        top_role_candidates: [{
          canonical_role_id: 'backend_engineering',
          canonical_role: '后端开发工程师',
          role_score: 0.86,
          representative_job: {
            id: 'job-v2', title: '高级后端开发工程师', job_family: '后端开发工程师', company_name: '示例企业', rerank_score: 0.86,
            search_metadata: { canonical_role_id: 'backend_engineering', canonical_role: '后端开发工程师', canonical_direction: '服务端与工程架构', match_explanation: { components: { 'Skill Match': { details: { matched_skills: ['Python'], missing_skills: ['Docker'] } }, 'Job Description Match': { score: 0.5 } } } },
          },
        }, {
          canonical_role_id: 'data_engineering',
          canonical_role: '数据工程师',
          role_score: 0.71,
          representative_job: {
            id: 'job-data', title: '数据工程师', job_family: '数据工程师', company_name: '示例企业', rerank_score: 0.71,
            search_metadata: { canonical_role_id: 'data_engineering', canonical_role: '数据工程师', canonical_direction: '数据工程', match_explanation: { components: { 'Skill Match': { details: { matched_skills: ['Python'], missing_skills: ['SQL'] } }, 'Job Description Match': { score: 0.4 } } } },
          },
        }],
      },
      jobs: [{
        id: 'job-v2',
        title: '高级后端开发工程师',
        job_family: '后端开发工程师',
        company_name: '示例企业',
        rerank_score: 0.86,
        search_metadata: {
          canonical_role_id: 'backend_engineering',
          canonical_role: '后端开发工程师',
          canonical_direction: '服务端与工程架构',
          match_explanation: {
            components: {
              'Skill Match': { details: { matched_skills: ['Python'], missing_skills: ['Docker'] } },
              'Job Description Match': { score: 0.5 },
            },
          },
        },
      }, {
        id: 'job-v2-secondary',
        title: '后端开发工程师（另一条 JD）',
        job_family: '后端开发工程师',
        company_name: '另一家企业',
        rerank_score: 0.42,
        search_metadata: {
          canonical_role_id: 'backend_engineering',
          canonical_role: '后端开发工程师',
          canonical_direction: '服务端与工程架构',
          match_explanation: {
            components: {
              'Skill Match': { details: { matched_skills: ['Python'], missing_skills: ['Agentic RL'] } },
              'Job Description Match': { score: 0.4 },
            },
          },
        },
      }],
    });

    const result = await diagnoseCandidate({ resumeFile: resume });

    expect(searchJobsWithResume).toHaveBeenCalledWith(
      expect.objectContaining({ query: expect.stringContaining('Python'), limit: 10 }),
      resume,
      'auto'
    );
    expect(result.pipeline.mode).toBe('canonical-two-stage');
    expect(result.matches).toHaveLength(2);
    expect(result.matches[0]).toMatchObject({
      role: '后端开发工程师',
      family: '服务端与工程架构',
      score: 86,
      roleScore: 86,
    });
    expect(result.matches[1]).toMatchObject({ role: '数据工程师', family: '数据工程' });
    expect(getJobRecommendations).not.toHaveBeenCalled();
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

    expect(uploadResume).toHaveBeenCalledWith(resume, 'auto');
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
