import axios from 'axios';
import { useAuthStore } from '../store/authStore';

const axiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
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
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
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
    getAll: () => axiosInstance.get('/traffic/junctions'),
    getById: (id: string) => axiosInstance.get(`/traffic/junctions/${id}`),
    create: (data: any) => axiosInstance.post('/traffic/junctions', data),
    update: (id: string, data: any) => axiosInstance.patch(`/traffic/junctions/${id}`, data),
  },
  traffic: {
    getReadings: (junctionId: string, limit: number = 20) => axiosInstance.get(`/traffic/readings/${junctionId}?limit=${limit}`),
    getAllReadings: (limit: number = 100) => axiosInstance.get(`/traffic/readings?limit=${limit}`),
    createReading: (data: any) => axiosInstance.post('/traffic/readings', data),
  },
  signals: {
    getPlans: () => axiosInstance.get('/signals/plans'),
    getByJunction: (junctionId: string) => axiosInstance.get(`/signals/junctions/${junctionId}`),
    setMode: (junctionId: string, mode: string) => axiosInstance.patch(`/signals/junctions/${junctionId}/mode`, { mode }),
    override: (junctionId: string, action: string, value: number = 5) =>
      axiosInstance.post(`/signals/junctions/${junctionId}/override`, { action, value }),
  },
  simulation: {
    start: (scenario: string = 'morning_peak') => axiosInstance.post('/simulation/start', { scenario_profile: scenario }),
    step: (steps: number = 1) => axiosInstance.post('/simulation/step', { steps }),
    stop: () => axiosInstance.post('/simulation/stop'),
    getState: () => axiosInstance.get('/simulation/state'),
    getMetrics: () => axiosInstance.get('/simulation/metrics'),
    reset: () => axiosInstance.post('/simulation/reset'),
  },
  ml: {
    detect: (formData: FormData) => axiosInstance.post('/ml/detect', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
    predict: (junctionId: string) => axiosInstance.get(`/ml/predict/${junctionId}`),
    trainStart: (episodes: number = 500, scenario: string = 'morning_peak') => axiosInstance.post('/ml/train/start', { num_episodes: episodes, scenario }),
    trainStop: () => axiosInstance.post('/ml/train/stop'),
    trainStatus: () => axiosInstance.get('/ml/train/status'),
    modelHealth: () => axiosInstance.get('/ml/models/health'),
  },
  alerts: {
    getAll: () => axiosInstance.get('/alerts'),
    acknowledge: (id: string) => axiosInstance.patch(`/alerts/${id}/acknowledge`),
    getStats: () => axiosInstance.get('/alerts/stats'),
  },
  emergency: {
    activate: (data: { priority: string; vehicle_type: string; route_junction_ids?: string[]; corridor?: string[] }) =>
      axiosInstance.post('/emergency/activate', data),
    deactivate: (id: string) => axiosInstance.post(`/emergency/deactivate/${id}`),
    getStatus: (id?: string) => id ? axiosInstance.get(`/emergency/status/${id}`) : axiosInstance.get('/emergency/status'),
    getHistory: (limit: number = 20) => axiosInstance.get(`/emergency/history?limit=${limit}`),
  },
  routing: {
    getRoute: (origin_lat: number, origin_lon: number, dest_lat: number, dest_lon: number) =>
      axiosInstance.post('/routing/route', { origin_lat, origin_lon, dest_lat, dest_lon }),
    getAlternatives: (origin_lat: number, origin_lon: number, dest_lat: number, dest_lon: number) =>
      axiosInstance.post('/routing/alternatives', { origin_lat, origin_lon, dest_lat, dest_lon }),
    getCongestion: () => axiosInstance.get('/routing/congestion'),
    broadcastVMS: (data: { panel_cluster: string; line1: string; line2: string; priority?: string }) =>
      axiosInstance.post('/routing/vms/broadcast', data),
    getActiveVMS: () => axiosInstance.get('/routing/vms/active'),
    getVMSHistory: () => axiosInstance.get('/routing/vms/history'),
  },
  users: {
    getAll: () => axiosInstance.get('/users'),
    updateRole: (id: string, role: string) => axiosInstance.patch(`/users/${id}/role?role=${role}`),
    updateStatus: (id: string, is_active: boolean) => axiosInstance.patch(`/users/${id}/status?is_active=${is_active}`),
  }
};
