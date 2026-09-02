import axios from 'axios';
import { useAuthStore } from '../store/authStore';

const axiosInstance = axios.create({
  baseURL: '/api/v1',
});

axiosInstance.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

export const api = {
  auth: {
    login: (email: string, password: string) => axiosInstance.post('/auth/login', { email, password }),
    register: (data: any) => axiosInstance.post('/auth/register', data),
    getMe: () => axiosInstance.get('/auth/me'),
    refreshToken: () => axiosInstance.post('/auth/refresh'),
  },
  junctions: {
    getAll: () => axiosInstance.get('/junctions'),
    getById: (id: string) => axiosInstance.get(`/junctions/${id}`),
    create: (data: any) => axiosInstance.post('/junctions', data),
    update: (id: string, data: any) => axiosInstance.put(`/junctions/${id}`, data),
  },
  traffic: {
    getReadings: (junctionId: string) => axiosInstance.get(`/traffic/readings/${junctionId}`),
    getLatest: () => axiosInstance.get('/traffic/latest'),
  },
  simulation: {
    start: () => axiosInstance.post('/simulation/start'),
    step: () => axiosInstance.post('/simulation/step'),
    stop: () => axiosInstance.post('/simulation/stop'),
    getState: () => axiosInstance.get('/simulation/state'),
    getMetrics: () => axiosInstance.get('/simulation/metrics'),
  },
  ml: {
    detect: (data: any) => axiosInstance.post('/ml/detect', data),
    predict: (junctionId: string) => axiosInstance.get(`/ml/predict/${junctionId}`),
    trainStart: () => axiosInstance.post('/ml/train/start'),
    trainStop: () => axiosInstance.post('/ml/train/stop'),
    trainStatus: () => axiosInstance.get('/ml/train/status'),
    modelHealth: () => axiosInstance.get('/ml/health'),
  },
  alerts: {
    getAll: () => axiosInstance.get('/alerts'),
    acknowledge: (id: string) => axiosInstance.post(`/alerts/${id}/acknowledge`),
    getStats: () => axiosInstance.get('/alerts/stats'),
  },
  emergency: {
    activate: (data: any) => axiosInstance.post('/emergency/activate', data),
    deactivate: (id: string) => axiosInstance.post(`/emergency/${id}/deactivate`),
    getStatus: () => axiosInstance.get('/emergency/status'),
    getHistory: () => axiosInstance.get('/emergency/history'),
  },
  routing: {
    getRoute: (start: [number, number], end: [number, number]) => axiosInstance.post('/routing/route', { start, end }),
    getAlternatives: (start: [number, number], end: [number, number]) => axiosInstance.post('/routing/alternatives', { start, end }),
  },
  users: {
    getAll: () => axiosInstance.get('/users'),
    updateRole: (id: string, role: string) => axiosInstance.put(`/users/${id}/role`, { role }),
    updateStatus: (id: string, is_active: boolean) => axiosInstance.put(`/users/${id}/status`, { is_active }),
  }
};
