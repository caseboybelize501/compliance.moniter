import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const controlsApi = {
  list: (framework, status) => 
    api.get('/api/controls', { params: { framework, status } }),
  get: (controlId) => 
    api.get(`/api/controls/${controlId}`),
};

export const violationsApi = {
  list: (severity, status) => 
    api.get('/api/violations', { params: { severity, status } }),
  get: (violationId) => 
    api.get(`/api/violations/${violationId}`),
};

export const evidenceApi = {
  get: (artifactId) => 
    api.get(`/api/evidence/${artifactId}`),
  download: (artifactId) => 
    api.get(`/api/evidence/${artifactId}/download`, { responseType: 'blob' }),
};

export const reportsApi = {
  generate: (data) => 
    api.post('/api/reports', data),
  download: (reportId) => 
    api.get(`/api/reports/${reportId}/download`, { responseType: 'blob' }),
};

export const integrationsApi = {
  list: () => 
    api.get('/api/integrations'),
  validate: (sourceType, credentials) => 
    api.post(`/api/integrations/${sourceType}/validate`, credentials),
};

export default api;
