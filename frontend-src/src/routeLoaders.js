// Keep route imports in one place so navigation can warm the same chunks used by React.lazy.
export const routeLoaders = Object.freeze({
  '/': () => import('./pages/DiagnosisPage'),
  '/recruitment': () => import('./pages/RecruitmentJobsPage'),
  '/candidates': () => import('./pages/CandidateMatchingPage'),
  '/signals': () => import('./pages/RoleEvolutionCenterPage'),
  '/jd-quality': () => import('./pages/JdQualityPage'),
  '/graph': () => import('./pages/GraphPage'),
  '/diagnosis': () => import('./pages/DiagnosisPage'),
  '/learning': () => import('./pages/LearningPlanPage'),
  '/legacy-home': () => import('./pages/HomePage'),
  '/search': () => import('./pages/SearchPage'),
  '/job': () => import('./pages/JobDetailsPage'),
  '/upload-resume': () => import('./pages/ResumeUploadPage'),
  '/recommendations': () => import('./pages/RecommendationsPage'),
  '/personalized-recommendations': () => import('./pages/PersonalizedRecommendationsPage'),
  '/fusion-demo': () => import('./pages/FusionDemoPage'),
  '/login': () => import('./pages/LoginPage'),
  '/register': () => import('./pages/RegisterPage'),
});

export const preloadRoute = (path) => {
  const routeKey = path.startsWith('/job/') ? '/job' : path;
  return routeLoaders[routeKey]?.();
};
