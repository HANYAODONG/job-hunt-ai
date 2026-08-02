import React from 'react';
import { BrowserRouter as Router, Navigate, Routes, Route, useOutletContext } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { App as AntdApp, ConfigProvider } from 'antd';
import 'antd/dist/reset.css';
import './App.css';

// Components
import WorkbenchLayout from './components/workbench/WorkbenchLayout';
import HomePage from './pages/HomePage';
import SearchPage from './pages/SearchPage';
import JobDetailsPage from './pages/JobDetailsPage';
import ResumeUploadPage from './pages/ResumeUploadPage';
import RecommendationsPage from './pages/RecommendationsPage';
import PersonalizedRecommendationsPage from './pages/PersonalizedRecommendationsPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DiscoveryPage from './pages/DiscoveryPage';
import GraphPage from './pages/GraphPage';
import DiagnosisPage from './pages/DiagnosisPage';
import LearningPlanPage from './pages/LearningPlanPage';
import RecruitmentJobsPage from './pages/RecruitmentJobsPage';
import CandidateMatchingPage from './pages/CandidateMatchingPage';

// Context
import { CandidateProvider } from './contexts/CandidateContext';
import { AuthProvider } from './contexts/AuthContext';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
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
              <Routes>
                <Route path="/" element={<WorkbenchLayout />}>
                  <Route index element={<WorkspaceHomeRedirect />} />
                  <Route path="recruitment" element={<RecruitmentJobsPage />} />
                  <Route path="candidates" element={<CandidateMatchingPage />} />
                  <Route path="signals" element={<DiscoveryPage />} />
                  <Route path="discovery" element={<Navigate replace to="/signals" />} />
                  <Route path="roles" element={<Navigate replace to="/graph" />} />
                  <Route path="graph" element={<GraphPage />} />
                  <Route path="evolution" element={<Navigate replace to="/signals" />} />
                  <Route path="diagnosis" element={<DiagnosisPage />} />
                  <Route path="learning" element={<LearningPlanPage />} />
                  <Route path="governance" element={<Navigate replace to="/" />} />
                  <Route path="evaluation" element={<Navigate replace to="/" />} />
                  <Route path="legacy-home" element={<HomePage />} />
                  <Route path="search" element={<SearchPage />} />
                  <Route path="job/:jobId" element={<JobDetailsPage />} />
                  <Route path="upload-resume" element={<ResumeUploadPage />} />
                  <Route path="recommendations" element={<RecommendationsPage />} />
                  <Route path="personalized-recommendations" element={<PersonalizedRecommendationsPage />} />
                  <Route path="login" element={<LoginPage />} />
                  <Route path="register" element={<RegisterPage />} />
                </Route>
              </Routes>
              </Router>
            </CandidateProvider>
          </AuthProvider>
        </AntdApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

export default App;
