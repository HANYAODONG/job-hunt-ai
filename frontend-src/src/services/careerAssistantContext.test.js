import {
  collectCareerAssistantContext,
  saveDiagnosisAssistantContext,
  saveLearningAssistantContext,
} from './careerAssistantContext';

beforeEach(() => localStorage.clear());

test('collects compact resume, matching gaps, and learning plan context', () => {
  saveDiagnosisAssistantContext({
    generatedAt: '2026-09-04',
    profile: { name: '测试用户', skills: ['Python', 'SQL'], yearsExperience: 2, experience: '数据项目经验' },
    matches: [{ id: 'r1', role: '后端开发工程师', score: 86, matchingSkills: ['Python'], gaps: [{ skill: 'Redis' }] }],
    pipeline: { mode: 'canonical-two-stage' },
  }, 'resume.pdf', 'r1');
  saveLearningAssistantContext({
    targetRole: '后端开发工程师',
    stages: [{ phase: '阶段1', skill: 'Redis', title: '缓存实践', tasks: ['完成缓存项目'] }],
  });

  const result = collectCareerAssistantContext({ page: '人岗诊断' });
  expect(result.hasData).toBe(true);
  expect(result.sections).toEqual(['简历画像', '岗位匹配', '能力缺口', '学习路径']);
  expect(result.context.resumeAnalysis.selectedMatch.missingSkills).toEqual(['Redis']);
  expect(result.context.learningPlan.stages[0].skill).toBe('Redis');
});
