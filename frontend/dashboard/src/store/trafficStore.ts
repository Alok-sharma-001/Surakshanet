import { create } from 'zustand';
import { Junction, JunctionState, Alert, SimulationState, TrainingStatus } from '../types';
import { api } from '../services/api';

interface TrafficState {
  junctions: Junction[];
  junctionStates: Record<string, JunctionState>;
  alerts: Alert[];
  simulationState: SimulationState | null;
  isSimulationRunning: boolean;
  trainingStatus: TrainingStatus | null;
  
  setJunctions: (junctions: Junction[]) => void;
  updateJunctionState: (state: JunctionState) => void;
  addAlert: (alert: Alert) => void;
  acknowledgeAlert: (id: string) => void;
  setSimulationState: (state: SimulationState) => void;
  setTrainingStatus: (status: TrainingStatus | null) => void;
  fetchJunctions: () => Promise<void>;
}

export const useTrafficStore = create<TrafficState>((set, get) => ({
  junctions: [],
  junctionStates: {},
  alerts: [],
  simulationState: null,
  isSimulationRunning: false,
  trainingStatus: null,

  setJunctions: (junctions) => set({ junctions }),
  
  updateJunctionState: (state) => set((prev) => ({
    junctionStates: { ...prev.junctionStates, [state.junction_id]: state }
  })),

  addAlert: (alert) => set((prev) => ({
    alerts: [alert, ...prev.alerts]
  })),

  acknowledgeAlert: (id) => set((prev) => ({
    alerts: prev.alerts.map(a => a.id === id ? { ...a, is_acknowledged: true } : a)
  })),

  setSimulationState: (state) => set({ 
    simulationState: state,
    isSimulationRunning: true // Assumes receiving state means running
  }),

  setTrainingStatus: (status) => set({ trainingStatus: status }),

  fetchJunctions: async () => {
    try {
      const res = await api.junctions.getAll();
      set({ junctions: res.data });
    } catch (e) {
      console.error('Failed to fetch junctions', e);
    }
  }
}));
