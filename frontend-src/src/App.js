import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ConfigProvider } from 'antd';
import 'antd/dist/reset.css';
import './App.css';

// Components
import Header from './components/Header';
import HomePage from './pages/HomePage';
import SearchPage from './pages/SearchPage';
import JobDetailsPage from './pages/JobDetailsPage';
import ResumeUploadPage from './pages/ResumeUploadPage';
import RecommendationsPage from './pages/RecommendationsPage';
import PersonalizedRecommendationsPage from './pages/PersonalizedRecommendationsPage';
import FusionDemoPage from './pages/FusionDemoPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';

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

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: '#1890ff',
            borderRadius: 6,
          },
        }}
      >
        <AuthProvider>
          <CandidateProvider>
            <Router>
              <div className="App">
                <Header />
                <main className="main-content">
                  <Routes>
                    <Route path="/" element={<HomePage />} />
                    <Route path="/search" element={<SearchPage />} />
                    <Route path="/job/:jobId" element={<JobDetailsPage />} />
                    <Route path="/upload-resume" element={<ResumeUploadPage />} />
                    <Route path="/recommendations" element={<RecommendationsPage />} />
                    <Route path="/personalized-recommendations" element={<PersonalizedRecommendationsPage />} />
                    <Route path="/fusion-demo" element={<FusionDemoPage />} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/register" element={<RegisterPage />} />
                  </Routes>
                </main>
              </div>
            </Router>
          </CandidateProvider>
        </AuthProvider>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

export default App;
