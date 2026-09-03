import { useState, useEffect, useCallback } from 'react';

/* ─────────────────────────────────────────────────────────────
   useTrafficSimulationEngine
   A shared lightweight background ticker that produces realistic
   real-time traffic telemetry data for the dashboard.
   ───────────────────────────────────────────────────────────── */

export interface TelemetryEvent {
  id: number;
  type: 'emergency' | 'info' | 'warning' | 'success';
  title: string;
  desc: string;
  time: string;
  timestamp: number;
}

export interface NetworkMetrics {
  totalVehicles: number;
  avgSpeed: number;
  networkLOS: string;
  losLabel: string;
  throughput: number;
  activeAlerts: number;
}

export interface SignalPhase {
  phaseId: number;
  phaseName: string;
  remaining: number;
  cycleLength: number;
}

const EVENT_TEMPLATES: Omit<TelemetryEvent, 'id' | 'timestamp'>[] = [
  { type: 'emergency', title: 'Ambulance Approaching', desc: 'J-42 pre-empted to Green (Phase 3). ETA 45s.', time: 'Just now' },
  { type: 'info', title: 'MARL Phase Adjustment', desc: 'Corridor Alpha cycle length increased by 12s to clear backlog.', time: '~2m' },
  { type: 'warning', title: 'Congestion Build-up', desc: 'Volume exceeding capacity at Link 104-B. Speed dropped to 15km/h.', time: '~5m' },
  { type: 'success', title: 'Sync Check Complete', desc: 'All 150 edge devices reporting nominal status.', time: '~12m' },
  { type: 'info', title: 'Green Wave Optimized', desc: 'Corridor Beta green-band re-timed for 42 km/h progression.', time: '~3m' },
  { type: 'warning', title: 'Queue Spillback Risk', desc: 'Junction A4 northbound queue at 78% capacity. Predicted overflow in 8m.', time: '~1m' },
  { type: 'success', title: 'Edge Firmware Update', desc: 'Node BLR-8821 firmware updated to v3.2.1 successfully.', time: '~15m' },
  { type: 'emergency', title: 'Fire Engine Dispatched', desc: 'Green corridor activated on Ring Road. 18 junctions pre-empted.', time: 'Just now' },
];

function randomBetween(min: number, max: number): number {
  return Math.round(min + Math.random() * (max - min));
}

function generateMetrics(): NetworkMetrics {
  const totalVehicles = randomBetween(22000, 27000);
  const avgSpeed = randomBetween(26, 40);
  const throughput = randomBetween(1000, 1500);
  const activeAlerts = randomBetween(2, 8);

  let networkLOS = 'C';
  let losLabel = 'Fair Flow';
  if (avgSpeed > 35) { networkLOS = 'B'; losLabel = 'Good Flow'; }
  else if (avgSpeed < 28) { networkLOS = 'D'; losLabel = 'Slow'; }

  return { totalVehicles, avgSpeed, networkLOS, losLabel, throughput, activeAlerts };
}

export function useTrafficSimulationEngine(intervalMs: number = 5000) {
  const [metrics, setMetrics] = useState<NetworkMetrics>(generateMetrics);
  const [events, setEvents] = useState<TelemetryEvent[]>(() =>
    EVENT_TEMPLATES.slice(0, 4).map((e, i) => ({ ...e, id: i, timestamp: Date.now() - i * 120000 }))
  );
  const [clock, setClock] = useState('');
  const [, setEventCounter] = useState(4);

  // Live clock
  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        })
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Metric updates
  useEffect(() => {
    const id = setInterval(() => setMetrics(generateMetrics()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  // Periodic new events
  useEffect(() => {
    const id = setInterval(() => {
      const template = EVENT_TEMPLATES[Math.floor(Math.random() * EVENT_TEMPLATES.length)];
      setEventCounter((c) => {
        const newEvent: TelemetryEvent = {
          ...template,
          id: c,
          time: 'Just now',
          timestamp: Date.now(),
        };
        setEvents((prev) => [newEvent, ...prev].slice(0, 20));
        return c + 1;
      });
    }, 15000);
    return () => clearInterval(id);
  }, []);

  const acknowledgeEvent = useCallback((eventId: number) => {
    setEvents((prev) => prev.filter((e) => e.id !== eventId));
  }, []);

  return { metrics, events, clock, acknowledgeEvent };
}

export function useSignalPhase(initialRemaining: number = 14, cycleLength: number = 120) {
  const PHASES = ['North-South Straight', 'North-South Left', 'East-West Straight', 'East-West Left'];
  const [phaseIdx, setPhaseIdx] = useState(0);
  const [remaining, setRemaining] = useState(initialRemaining);

  useEffect(() => {
    const id = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          setPhaseIdx((p) => (p + 1) % PHASES.length);
          return randomBetween(10, 25);
        }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return {
    phaseId: phaseIdx,
    phaseName: PHASES[phaseIdx],
    remaining,
    cycleLength,
  } as SignalPhase;
}
