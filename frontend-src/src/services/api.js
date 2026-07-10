import axios from 'axios';
import { getMockSearchResults, mockApiDelay } from '../data/mockJobData';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
const USE_MOCK_DATA = process.env.REACT_APP_USE_MOCK_DATA === 'true';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

const isBackendUnavailable = (error) => {
  return !error.response ||
    error.code === 'ECONNREFUSED' ||
    error.code === 'ETIMEDOUT' ||
    error.code === 'ECONNABORTED' ||
    error.message.includes('Network Error');
};

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    
    // Check if it's a network error or backend unavailable
    if (isBackendUnavailable(error)) {
      console.warn('Backend unavailable for this request');
    }
    
    return Promise.reject(error);
  }
);

// Job Search API
export const searchJobs = async (searchParams) => {
  try {
    const response = await api.post('/jobs/search', searchParams, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  } catch (error) {
    // If backend is not responding, use mock data
    if (USE_MOCK_DATA && isBackendUnavailable(error)) {
      console.warn('Using mock data - Backend unavailable');
      await mockApiDelay();
      return getMockSearchResults(searchParams, false);
    }
    throw new Error(error.response?.data?.detail || 'Failed to search jobs');
  }
};

export const searchJobsWithResume = async (searchParams, resumeFile) => {
  try {
    const formData = new FormData();
    formData.append('resume_file', resumeFile);
    formData.append('query', JSON.stringify(searchParams));
    
    const response = await api.post('/jobs/search-with-resume', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  } catch (error) {
    // If backend is not responding, use mock data
    if (USE_MOCK_DATA && isBackendUnavailable(error)) {
      console.warn('Using mock data - Backend unavailable');
      await mockApiDelay();
      return getMockSearchResults(searchParams, false);
    }
    throw new Error(error.response?.data?.detail || 'Failed to search jobs with resume');
  }
};

export const getJobById = async (jobId) => {
  try {
    const response = await api.get(`/jobs/${jobId}`);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get job details');
  }
};

export const getSimilarJobs = async (jobId, limit = 10) => {
  try {
    const response = await api.get(`/jobs/${jobId}/similar?limit=${limit}`);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get similar jobs');
  }
};

// Resume Processing API
export const uploadResume = async (resumeFile) => {
  try {
    const formData = new FormData();
    formData.append('resume_file', resumeFile);
    
    const response = await api.post('/jobs/upload-resume', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to upload resume');
  }
};

export const getResumeInsights = async (candidateId) => {
  try {
    const response = await api.get(`/jobs/resume-insights/${candidateId}`);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get resume insights');
  }
};

// Job Recommendations API
export const getJobRecommendations = async (candidate) => {
  try {
    const response = await api.post('/jobs/recommendations', candidate);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get job recommendations');
  }
};

// Market Trends API
export const getMarketTrends = async (skill) => {
  try {
    const response = await api.get(`/jobs/market-trends/${skill}`);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get market trends');
  }
};

// Job Management API (for admin use)
export const createJob = async (job) => {
  try {
    const response = await api.post('/jobs/', job);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to create job');
  }
};

export const updateJob = async (jobId, job) => {
  try {
    const response = await api.put(`/jobs/${jobId}`, job);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to update job');
  }
};

export const deleteJob = async (jobId) => {
  try {
    const response = await api.delete(`/jobs/${jobId}`);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to delete job');
  }
};

export const bulkCreateJobs = async (jobs) => {
  try {
    const response = await api.post('/jobs/bulk', jobs);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to bulk create jobs');
  }
};

// Reranking API
export const searchJobsWithReranking = async (searchParams, userDescription = null, includeExplanations = false) => {
  try {
    const params = new URLSearchParams();
    if (userDescription) params.append('user_description', userDescription);
    if (includeExplanations) params.append('include_explanations', 'true');

    // Wrap searchParams in search_query as expected by backend
    const requestBody = {
      search_query: searchParams
    };

    const response = await api.post(`/reranking/search-reranked?${params.toString()}`, requestBody, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  } catch (error) {
    // If backend is not responding, use mock data
    if (USE_MOCK_DATA && isBackendUnavailable(error)) {
      console.warn('Using mock data - Backend unavailable');
      await mockApiDelay();
      return getMockSearchResults(searchParams, true);
    }
    throw new Error(error.response?.data?.detail || 'Failed to search jobs with reranking');
  }
};

export const searchJobsWithRerankingAndResume = async (searchParams, resumeFile, userDescription = null, includeExplanations = false) => {
  try {
    const formData = new FormData();
    formData.append('resume_file', resumeFile);
    
    // Add search parameters to form data
    formData.append('query', searchParams.query);
    if (searchParams.location) formData.append('location', searchParams.location);
    if (searchParams.min_salary) formData.append('min_salary', searchParams.min_salary.toString());
    if (searchParams.job_type) formData.append('job_type', searchParams.job_type);
    if (searchParams.experience_level) formData.append('experience_level', searchParams.experience_level);
    if (searchParams.remote_allowed !== undefined && searchParams.remote_allowed !== null) {
      formData.append('remote_allowed', searchParams.remote_allowed.toString());
    }
    if (searchParams.visa_sponsorship !== undefined && searchParams.visa_sponsorship !== null) {
      formData.append('visa_sponsorship', searchParams.visa_sponsorship.toString());
    }
    formData.append('page', searchParams.page.toString());
    formData.append('page_size', searchParams.page_size.toString());
    
    // Add optional parameters
    if (userDescription) formData.append('user_description', userDescription);
    formData.append('include_explanations', includeExplanations.toString());
    
    const response = await api.post('/reranking/search-reranked-with-resume', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  } catch (error) {
    // If backend is not responding, use mock data
    if (USE_MOCK_DATA && isBackendUnavailable(error)) {
      console.warn('Using mock data - Backend unavailable');
      await mockApiDelay();
      return getMockSearchResults(searchParams, true);
    }
    console.error('Detailed error:', error);
    console.error('Error response:', error.response);
    console.error('Error response data:', error.response?.data);
    throw new Error(error.response?.data?.detail || error.response?.data?.message || error.message || 'Failed to search jobs with reranking and resume');
  }
};

export const getPersonalizedRecommendations = async (resumeFile, userDescription = null, limit = 10, includeExplanations = true) => {
  try {
    const formData = new FormData();
    formData.append('resume_file', resumeFile);
    
    // Add form parameters
    if (userDescription) formData.append('user_description', userDescription);
    formData.append('limit', limit.toString());
    formData.append('include_explanations', includeExplanations.toString());
    
    const response = await api.post('/reranking/personalized-recommendations', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get personalized recommendations');
  }
};

export const getRerankingExplanation = async (jobId, userDescription = null, resumeFile = null) => {
  try {
    const params = new URLSearchParams();
    if (userDescription) params.append('user_description', userDescription);
    
    const formData = new FormData();
    if (resumeFile) {
      formData.append('resume_file', resumeFile);
    }
    
    const response = await api.post(
      `/reranking/reranking-explanation/${jobId}?${params.toString()}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get reranking explanation');
  }
};

export const getRerankingWeights = async () => {
  try {
    const response = await api.get('/reranking/reranking-weights');
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get reranking weights');
  }
};

export const updateRerankingWeights = async (weights) => {
  try {
    const response = await api.put('/reranking/reranking-weights', weights);
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to update reranking weights');
  }
};

export const getRerankingStatistics = async () => {
  try {
    const response = await api.get('/reranking/reranking-statistics');
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get reranking statistics');
  }
};

// Authentication API
export const registerUser = async (userData) => {
  try {
    const response = await api.post('/auth/register', userData, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Registration failed');
  }
};

export const loginUser = async (credentials) => {
  try {
    const response = await api.post('/auth/login', credentials, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Login failed');
  }
};

export const getCurrentUser = async (token) => {
  try {
    const response = await api.get('/auth/me', {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get user info');
  }
};

export const applyToJob = async (jobId, applicationData, token) => {
  try {
    const response = await api.post(`/auth/apply/${jobId}`, applicationData, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to apply to job');
  }
};

export const getUserApplications = async (token) => {
  try {
    const response = await api.get('/auth/applications', {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Failed to get applications');
  }
};

// Keyword Extraction API
export const extractKeywords = async (query) => {
  try {
    const response = await api.post('/keyword-extraction/extract', {
      query: query
    }, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  } catch (error) {
    console.error('Error extracting keywords:', error);
    throw new Error(error.response?.data?.detail || 'Failed to extract keywords');
  }
};

// Rerank with Keywords API
export const rerankWithKeywords = async (searchResults, selectedKeywords) => {
  try {
    const response = await api.post('/reranking/rerank-with-keywords', {
      search_results: searchResults,
      keywords: selectedKeywords
    }, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  } catch (error) {
    console.error('Error reranking with keywords:', error);
    throw new Error(error.response?.data?.detail || 'Failed to rerank with keywords');
  }
};

// Health Check API
export const healthCheck = async () => {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    throw new Error('Health check failed');
  }
};

export default api;
