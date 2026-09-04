import React, { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Navigate, Routes, Route, useOutletContext } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { App as AntdApp, ConfigProvider } from 'antd';
import 'antd/dist/reset.css';
import './App.css';
import { CandidateProvider } from './contexts/CandidateContext';
import { AuthProvider } from './contexts/AuthContext';
import { routeLoaders } from './routeLoaders';

// Components
import WorkbenchLayout from './components/workbench/WorkbenchLayout';
const HomePage = lazy(routeLoaders['/legacy-home']);
const SearchPage = lazy(routeLoaders['/search']);
const JobDetailsPage = lazy(routeLoaders['/job']);
const ResumeUploadPage = lazy(routeLoaders['/upload-resume']);
const RecommendationsPage = lazy(routeLoaders['/recommendations']);
const PersonalizedRecommendationsPage = lazy(routeLoaders['/personalized-recommendations']);
const FusionDemoPage = lazy(routeLoaders['/fusion-demo']);
const LoginPage = lazy(routeLoaders['/login']);
const RegisterPage = lazy(routeLoaders['/register']);
const RoleEvolutionCenterPage = lazy(routeLoaders['/signals']);
const JdQualityPage = lazy(routeLoaders['/jd-quality']);
const GraphPage = lazy(routeLoaders['/graph']);
const DiagnosisPage = lazy(routeLoaders['/diagnosis']);
const LearningPlanPage = lazy(routeLoaders['/learning']);
const RecruitmentJobsPage = lazy(routeLoaders['/recruitment']);
const CandidateMatchingPage = lazy(routeLoaders['/candidates']);
const RuntimeSettingsPage = lazy(routeLoaders['/settings']);

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 60 * 1000,
      cacheTime: 30 * 60 * 1000,
    },
  },
});

const WorkspaceHomeRedirect = () => {
  const { workspaceRole = 'candidate' } = useOutletContext() || {};
  return <Navigate replace to={workspaceRole === 'enterprise' ? '/recruitment' : '/diagnosis'} />;
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: '#0066ff',
            colorInfo: '#0066ff',
            colorSuccess: '#16846b',
            colorWarning: '#b96b18',
            colorError: '#bf5a45',
            colorText: '#17191d',
            colorTextSecondary: '#626872',
            colorBorder: '#d8dad6',
            borderRadius: 5,
            fontFamily: "Inter, 'PingFang SC', 'Microsoft YaHei', sans-serif",
          },
        }}
      >
        <AntdApp>
          <AuthProvider>
            <CandidateProvider>
              <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
              <Suspense fallback={<div className="route-loading" role="status">正在加载工作台...</div>}>
                <Routes>
                  <Route path="/" element={<WorkbenchLayout />}>
                  <Route index element={<WorkspaceHomeRedirect />} />
                  <Route path="recruitment" element={<RecruitmentJobsPage />} />
                  <Route path="candidates" element={<CandidateMatchingPage />} />
                  <Route path="signals" element={<RoleEvolutionCenterPage />} />
                  <Route path="jd-quality" element={<JdQualityPage />} />
                  <Route path="discovery" element={<Navigate replace to="/signals" />} />
                  <Route path="roles" element={<Navigate replace to="/graph" />} />
                  <Route path="graph" element={<GraphPage />} />
                  <Route path="evolution" element={<Navigate replace to="/signals" />} />
                  <Route path="diagnosis" element={<DiagnosisPage />} />
                  <Route path="learning" element={<LearningPlanPage />} />
                  <Route path="settings" element={<RuntimeSettingsPage />} />
                  <Route path="governance" element={<Navigate replace to="/" />} />
                  <Route path="evaluation" element={<Navigate replace to="/" />} />
                  <Route path="legacy-home" element={<HomePage />} />
                  <Route path="search" element={<SearchPage />} />
                  <Route path="job/:jobId" element={<JobDetailsPage />} />
                  <Route path="upload-resume" element={<ResumeUploadPage />} />
                  <Route path="recommendations" element={<RecommendationsPage />} />
                  <Route path="personalized-recommendations" element={<PersonalizedRecommendationsPage />} />
                  <Route path="fusion-demo" element={<FusionDemoPage />} />
                  <Route path="login" element={<LoginPage />} />
                  <Route path="register" element={<RegisterPage />} />
                  </Route>
                </Routes>
              </Suspense>
              </Router>
            </CandidateProvider>
          </AuthProvider>
        </AntdApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

export default App;
