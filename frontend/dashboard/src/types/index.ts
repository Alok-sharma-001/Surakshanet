export interface User {
  id: string;
  email: string;
  name: string;
  role: 'ADMIN' | 'OPERATOR' | 'VIEWER';
  is_active: boolean;
  created_at: string;
}

export interface Junction {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  num_approaches: number;
  is_active: boolean;
  created_at: string;
}

export interface TrafficReading {
  id: string;
  timestamp: string;
  sensor_id: string;
  junction_id: string;
  vehicle_count: number;
  pcu_value: number;
  avg_speed: number | null;
  queue_length: number | null;
  vehicle_breakdown: Record<string, number> | null;
}

export interface JunctionState {
  junction_id: string;
  timestamp: number;
  approaches: Record<string, { pcu: number; queue_length: number; avg_speed: number }>;
  current_phase: string;
  phase_elapsed: number;
  mode: string;
}

export interface Alert {
  id: string;
  junction_id: string | null;
  alert_type: 'CONGESTION' | 'SPILLBACK' | 'SIGNAL_FAILURE' | 'QUEUE_OVERFLOW';
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  message: string;
  is_acknowledged: boolean;
  created_at: string;
  acknowledged_at: string | null;
}

export interface EmergencyEvent {
  id: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM';
  vehicle_type: 'AMBULANCE' | 'FIRE' | 'POLICE' | 'VIP';
  route: string[];
  status: 'ACTIVE' | 'COMPLETED' | 'CANCELLED';
  activated_by: string | null;
  started_at: string;
  ended_at: string | null;
}

export interface Prediction {
  minutes: number;
  predicted_pcu: number;
  confidence: number;
}

export interface TrainingStatus {
  is_training: boolean;
  episode: number;
  total_episodes: number;
  current_reward: number;
  avg_reward_100: number;
  epsilon: number;
  best_reward: number;
}

export interface Route {
  path: [number, number][];
  distance_km: number;
  eta_minutes: number;
  congestion_level: string;
}

export interface SimulationState {
  simulation_time: number;
  step_count: number;
  junctions: Record<string, JunctionState>;
  global_metrics: {
    total_vehicles: number;
    avg_speed: number;
    total_waiting_time: number;
    throughput: number;
  };
}
