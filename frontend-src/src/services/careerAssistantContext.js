const DIAGNOSIS_KEY = 'careerAssistantDiagnosis';
const LEARNING_KEY = 'careerAssistantLearningPlan';

const readJson = (key) => {
  try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch { return null; }
};

const strings = (items, limit = 20) => (Array.isArray(items) ? items : [])
  .map((item) => String(item?.name || item?.skill || item || '').trim())
  .filter(Boolean)
  .slice(0, limit);

export const saveDiagnosisAssistantContext = (analysis, resumeName, selectedRoleId = null) => {
  if (!analysis) return;
  const previous = readJson(DIAGNOSIS_KEY);
  const matches = (analysis.matches || []).slice(0, 3);
  const selected = matches.find((item) => item.id === selectedRoleId) || matches[0] || null;
  const compact = {
    importedAt: new Date().toLocaleString('zh-CN', { hour12: false }),
    resume: {
      fileName: resumeName || previous?.resume?.fileName || '已上传简历',
      candidateName: analysis.profile?.name || '',
      skills: strings(analysis.profile?.skills, 30),
      yearsExperience: analysis.profile?.yearsExperience || null,
      experienceSummary: String(analysis.profile?.experience || '').slice(0, 800),
    },
    selectedMatch: selected ? {
      role: selected.role,
      jobTitle: selected.jobTitle || selected.job?.title || '',
      company: selected.company || '',
      score: selected.score,
      roleScore: selected.roleScore,
      evidenceCoverage: selected.evidenceCoverage,
      matchedSkills: strings(selected.matchingSkills, 20),
      missingSkills: strings((selected.gaps || []).map((gap) => gap.skill), 15),
      reason: String(selected.reason || '').slice(0, 600),
      version: selected.version || '',
    } : null,
    alternativeMatches: matches.filter((item) => item.id !== selected?.id).map((item) => ({
      role: item.role,
      score: item.score,
      missingSkills: strings((item.gaps || []).map((gap) => gap.skill), 8),
    })),
    pipeline: analysis.pipeline?.mode || '',
    generatedAt: analysis.generatedAt || '',
  };
  localStorage.setItem(DIAGNOSIS_KEY, JSON.stringify(compact));
  window.dispatchEvent(new CustomEvent('career-analysis-updated'));
};

export const saveLearningAssistantContext = (plan) => {
  if (!plan) return;
  const compact = {
    importedAt: new Date().toLocaleString('zh-CN', { hour12: false }),
    targetRole: plan.targetRole,
    targetVersion: plan.targetVersion,
    matchScore: plan.matchScore,
    progress: plan.progress,
    currentStage: plan.currentStage,
    stages: (plan.stages || []).slice(0, 6).map((stage) => ({
      phase: stage.phase,
      skill: stage.skill,
      title: stage.title,
      status: stage.status,
      goal: String(stage.goal || '').slice(0, 350),
      tasks: strings(stage.tasks, 6),
      outcome: stage.outcome,
    })),
  };
  localStorage.setItem(LEARNING_KEY, JSON.stringify(compact));
  window.dispatchEvent(new CustomEvent('career-analysis-updated'));
};

export const collectCareerAssistantContext = (pageContext = {}) => {
  const diagnosis = readJson(DIAGNOSIS_KEY);
  const learningPlan = readJson(LEARNING_KEY);
  const legacyProfile = readJson('candidateProfile');
  const fallbackResume = legacyProfile ? {
    candidateName: legacyProfile.candidate?.name || '',
    skills: strings(legacyProfile.extracted_skills || legacyProfile.candidate?.skills, 30),
    yearsExperience: legacyProfile.candidate?.years_experience || null,
    experienceSummary: String(legacyProfile.experience_summary || '').slice(0, 800),
  } : null;
  const context = {
    ...pageContext,
    resumeAnalysis: diagnosis || (fallbackResume ? { resume: fallbackResume } : null),
    learningPlan,
  };
  const sections = [
    context.resumeAnalysis?.resume ? '简历画像' : null,
    context.resumeAnalysis?.selectedMatch ? '岗位匹配' : null,
    context.resumeAnalysis?.selectedMatch?.missingSkills?.length ? '能力缺口' : null,
    learningPlan?.stages?.length ? '学习路径' : null,
  ].filter(Boolean);
  return { context, sections, hasData: sections.length > 0 };
};
