import { useEffect, useState } from 'react';
import { Play, Square, FastForward, RotateCcw, Activity, Clock, Car, BarChart3, Gauge, AlertTriangle } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import clsx from 'clsx';
import { api } from '../services/api';
import { wsService } from '../services/websocket';
import { TelemetrySourceBadge } from '../components/TelemetrySourceBadge';

// A dash, not a number. Every tile on this page used to render a fixed
// figure, and the throughput chart plotted a generated sine wave under the
// heading "Real-time Throughput". Nothing was ever fetched from the API.
const DASH = '—';

const fmt = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? DASH : v.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

// This page used to have exactly one simulation: a private SUMO the API
// process started on demand, polled every 2s. It turned out to be a
// completely different simulation from the one operators actually watch —
// simulation/sumo_live_bridge.py, a separate host process with the real
// TraCI connection that feeds the Live Traffic Map, the control service, and
// emergency corridors. Stopping the bridge's SUMO changed nothing here,
// because this page was never watching it. Fixed by splitting the page in
// two: Pane A genuinely observes AND controls the bridge (pause/resume/step
// its real stepping loop, fire-and-forget over the same Redis command
// channel the control service already uses — the API still cannot start,
// stop, or reset the process itself, since it's a separate host process
// launched by start.sh/stop.sh); Pane B is the pre-existing scenario
// sandbox (SN-133), relabeled so it can no longer be mistaken for the
// corridor simulation judges see on screen.

interface BridgeLive {
  status: 'live' | 'connecting' | 'stale' | 'unavailable';
  reason: string | null;
  source: string | null;
  tick_age_s: number | null;
  heartbeat_age_s: number | null;
  step: number | null;
  sim_time_s: number | null;
  total_vehicles: number | null;
  avg_speed: number | null;
  mean_accumulated_wait_s: number | null;
  throughput: number | null;
  network_los: string | null;
  queue_length: number | null;
  config: string | null;
  seed: number | null;
  run_state: 'RUNNING' | 'PAUSED' | null;
  last_step: number | null;
  last_tick_age_s: number | null;
}

const STATUS_LABEL: Record<BridgeLive['status'], string> = {
  live: 'Live',
  connecting: 'Connecting',
  stale: 'Stale',
  unavailable: 'Unavailable',
};

// Local socket silence this long is attributed to the browser's own
// connection, never to the bridge — REST status is the authority on whether
// the bridge itself is alive.
const LOCAL_FEED_INTERRUPTED_MS = 5000;

function BridgeObserverPane() {
  const [live, setLive] = useState<BridgeLive | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [history, setHistory] = useState<{ step: number; throughput: number }[]>([]);
  const [wsLastMessageAt, setWsLastMessageAt] = useState<number | null>(null);
  const [nowTick, setNowTick] = useState(() => Date.now());
  const [commandError, setCommandError] = useState<string | null>(null);
  const [commandBusy, setCommandBusy] = useState(false);

  const refreshLive = async () => {
    try {
      const res = await api.simulation.getLive();
      setLive(res.data);
      setLiveError(null);
    } catch (err: any) {
      setLive(null);
      setLiveError(err?.response?.data?.detail ?? 'Bridge observer unavailable.');
    }
  };

  useEffect(() => {
    refreshLive();
    const t = setInterval(refreshLive, 2000);
    return () => clearInterval(t);
  }, []);

  // Fire-and-forget: the bridge's command protocol has no acknowledgement,
  // so a successful call here only means the command was published, not
  // that it was applied. refreshLive() right after is what shows the real
  // effect via run_state — same honesty discipline as the rest of this pane.
  const runCommand = async (fn: () => Promise<unknown>) => {
    setCommandBusy(true);
    setCommandError(null);
    try {
      await fn();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setCommandError(typeof detail === 'object' ? (detail?.reason ?? JSON.stringify(detail)) : (detail ?? 'Command failed.'));
    }
    setCommandBusy(false);
    refreshLive();
  };

  const isPaused = live?.run_state === 'PAUSED';
  const pauseBridge = () => runCommand(api.simulation.pauseLive);
  const resumeBridge = () => runCommand(api.simulation.resumeLive);
  const stepBridge = () => runCommand(() => api.simulation.stepLive(1));

  // Purely browser-local: this needs no clock agreement with the server or
  // the bridge. It only ever says something about THIS socket, never about
  // the bridge's own health — see the attribution rule below.
  useEffect(() => {
    const unsubscribe = wsService.onMessage('simulation', () => {
      setWsLastMessageAt(Date.now());
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    const t = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const isLive = live?.status === 'live';
  const localFeedAgeMs = wsLastMessageAt !== null ? nowTick - wsLastMessageAt : null;
  const feedInterrupted = isLive && (localFeedAgeMs === null || localFeedAgeMs > LOCAL_FEED_INTERRUPTED_MS);

  useEffect(() => {
    if (!isLive || live?.throughput === null || live?.throughput === undefined || live?.step === null || live?.step === undefined) return;
    setHistory((h) => {
      if (h.length && h[h.length - 1].step === live.step) return h;
      return [...h.slice(-99), { step: live.step as number, throughput: live.throughput as number }];
    });
  }, [isLive, live?.step, live?.throughput]);

  return (
    <section className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Live corridor bridge</h2>
          <p className="text-xs text-slate-500">
            The real SUMO simulation — same process as the SUMO GUI window, the Live Traffic Map, and the control
            service. Launched with <code className="font-mono">./start.sh</code>; Pause/Resume/Step below control its
            real stepping loop. Only a full stop/restart or a scenario change requires the simulation host directly.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-2">
            <button
              className={clsx(
                "p-2 rounded-lg transition-colors disabled:opacity-40",
                isPaused ? "bg-emerald-100 text-emerald-600 hover:bg-emerald-200" : "bg-amber-100 text-amber-600 hover:bg-amber-200"
              )}
              onClick={isPaused ? resumeBridge : pauseBridge}
              disabled={!isLive || commandBusy}
              title={isPaused ? "Resume" : "Pause"}
            >
              {isPaused ? <Play className="w-5 h-5" fill="currentColor" /> : <Square className="w-4 h-4" fill="currentColor" />}
            </button>
            <button
              className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-40"
              title="Step"
              onClick={stepBridge}
              disabled={!isLive || commandBusy}
            >
              <FastForward className="w-5 h-5" />
            </button>
          </div>
          <span className={clsx(
            'px-3 py-1 text-sm font-semibold rounded-full',
            isLive ? (isPaused ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700') : 'bg-slate-100 text-slate-700'
          )}>
            {isLive ? (isPaused ? 'Paused' : 'Live') : (live ? STATUS_LABEL[live.status] : 'Unavailable')}
          </span>
        </div>
      </div>

      {commandError && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-700">
          {commandError}
        </div>
      )}

      {!isLive && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex gap-3">
          <AlertTriangle className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
          <div className="text-sm text-slate-600">
            <p>{liveError ?? live?.reason ?? 'The live SUMO bridge is not reachable.'}</p>
            {live?.tick_age_s !== null && live?.tick_age_s !== undefined && (
              <p className="mt-1 text-xs text-slate-400">last tick {live.tick_age_s.toFixed(1)}s ago</p>
            )}
            {live?.heartbeat_age_s !== null && live?.heartbeat_age_s !== undefined && (
              <p className="text-xs text-slate-400">bridge heartbeat {live.heartbeat_age_s.toFixed(1)}s ago</p>
            )}
            {live?.last_step !== null && live?.last_step !== undefined && (
              <p className="mt-1 text-xs text-slate-400">
                last observed step {live.last_step}{live.last_tick_age_s !== null && live.last_tick_age_s !== undefined ? `, ${live.last_tick_age_s.toFixed(1)}s ago` : ''}
              </p>
            )}
          </div>
        </div>
      )}

      {feedInterrupted && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-700">
          Live feed interrupted — reconnecting. The bridge itself is still reporting live; this browser's WebSocket has gone quiet.
        </div>
      )}

      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5 flex flex-wrap gap-8">
        <div>
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Step</div>
          <div className="font-mono text-xl font-bold text-slate-900">{isLive ? fmt(live?.step) : DASH}</div>
        </div>
        <div>
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Sim Time</div>
          <div className="font-mono text-xl font-bold text-slate-900">{isLive ? `${fmt(live?.sim_time_s)}s` : DASH}</div>
        </div>
        <div>
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Config</div>
          <div className="font-mono text-sm font-bold text-slate-900">{isLive ? (live?.config ?? DASH) : DASH}</div>
        </div>
        <div>
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Seed</div>
          <div className="font-mono text-xl font-bold text-slate-900">{isLive ? fmt(live?.seed) : DASH}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Car className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Vehicles</h3>
            <TelemetrySourceBadge source={isLive ? (live?.source ?? null) : null} showIcon={false} />
          </div>
          <div className="text-4xl font-bold text-slate-900 mt-2">{isLive ? fmt(live?.total_vehicles) : DASH}</div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Gauge className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Avg Speed</h3>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <div className="text-4xl font-bold text-slate-900">{isLive ? fmt(live?.avg_speed, 1) : DASH}</div>
            <div className="text-sm font-medium text-slate-500">km/h</div>
          </div>
          {isLive && live?.avg_speed === null && (
            <p className="text-xs text-slate-400 mt-1">no vehicles in network to measure</p>
          )}
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Clock className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Mean Accumulated Wait</h3>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <div className="text-4xl font-bold text-slate-900">{isLive ? fmt(live?.mean_accumulated_wait_s, 1) : DASH}</div>
            <div className="text-sm font-medium text-slate-500">s</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <BarChart3 className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Throughput</h3>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <div className="text-4xl font-bold text-slate-900">{isLive ? fmt(live?.throughput) : DASH}</div>
            <div className="text-sm font-medium text-slate-500">veh/h</div>
          </div>
          {isLive && live?.throughput === null && (
            <p className="text-xs text-slate-400 mt-1">needs 60s of measured span</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Network LOS</h3>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">{isLive ? (live?.network_los ?? DASH) : DASH}</div>
        </div>
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Car className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Vehicles Below 5 km/h</h3>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">{isLive ? fmt(live?.queue_length) : DASH}</div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
        <h3 className="text-sm font-semibold text-slate-800 mb-4">Throughput history</h3>
        {!history.length && (
          <p className="text-xs text-slate-400 mb-2">
            No samples yet. History accumulates while the bridge is live.
          </p>
        )}
        <div className="h-[240px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={history} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="step" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0' }}
                labelStyle={{ color: '#64748b', fontWeight: 500, marginBottom: '4px' }}
              />
              <Line type="monotone" dataKey="throughput" stroke="#0284c7" strokeWidth={2} dot={false} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}

interface SimState {
  running?: boolean;
  step?: number;
  step_count?: number;
  sim_time?: string;
  simulation_time?: number;
  vehicles?: number;
  source?: string;
  scenario?: string;
  scenario_id?: string;
  seed?: number;
  step_age_s?: number | null;
  sandbox_fault?: string | null;
}

interface SimMetrics {
  throughput?: number | null;
  avg_delay?: number | null;
  avg_speed?: number | null;
  total_vehicles?: number | null;
  queue_length?: number | null;
  source?: string;
}

interface DemoScenario {
  id: string;
  name: string;
  description: string;
  seed: number;
  duration_s: number | null;
  mechanism: string;
}

// A running sandbox that has not genuinely advanced for this long is treated
// as stalled, not as a slow-but-honest reading — matches the bridge pane's
// staleness discipline (shared/constants.py::BRIDGE_TICK_STALE_AFTER_S).
const SANDBOX_STALE_AFTER_S = 3.0;

// SN-133: the dropdown lists whatever GET /simulation/scenarios returns —
// never a hardcoded label set. The page previously offered "Peak Hour /
// Off-Peak / Emergency / Festival", none of which corresponded to a real
// scenario or did anything when selected.
function ScenarioSandboxPane() {
  const [state, setState] = useState<SimState | null>(null);
  const [metrics, setMetrics] = useState<SimMetrics | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [throughputHistory, setThroughputHistory] = useState<{ step: number; throughput: number }[]>([]);
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('');
  const [switching, setSwitching] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const isRunning = state?.running === true;
  const isStale = isRunning && (state?.step_age_s ?? 0) > SANDBOX_STALE_AFTER_S;
  const isLive = isRunning && !isStale;

  const refresh = async () => {
    try {
      const res = await api.simulation.getState();
      setState(res.data);
      setUnavailable(null);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setUnavailable(
        typeof detail === 'object' && detail?.reason
          ? detail.reason
          : 'Simulation unavailable.'
      );
      setState(null);
    }
    try {
      const res = await api.simulation.getMetrics();
      setMetrics(res.data);
    } catch {
      // 503 while nothing is running is the expected case, not an error.
      setMetrics(null);
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    api.simulation.getScenarios()
      .then((res) => {
        const list: DemoScenario[] = res.data?.scenarios ?? [];
        setScenarios(list);
        if (list.length && !selectedScenarioId) setSelectedScenarioId(list[0].id);
      })
      .catch(() => setScenarios([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Built from measured samples as they arrive, never pre-filled, and only
  // while the sandbox is genuinely advancing (not stalled).
  useEffect(() => {
    if (!isLive || metrics?.throughput === null || metrics?.throughput === undefined) return;
    setThroughputHistory((h) => [
      ...h.slice(-99),
      { step: state?.step_count ?? state?.step ?? h.length, throughput: metrics.throughput as number },
    ]);
  }, [isLive, metrics?.throughput, state?.step_count, state?.step]);

  // SN-133: select -> state reset -> start at seed 42 (server-enforced,
  // never client-supplied). Completes in one click.
  //
  // Only stop() before starting, never a separate reset() in between:
  // SumoEnvironment.reset() (called by POST /simulation/reset) itself
  // stops then immediately restarts the PREVIOUS net/route files, which
  // leaves the simulation "running" again and makes the follow-up
  // startScenario() call fail with 409 "already running". POST
  // /simulation/start already tears down and replaces sim_instance with a
  // fresh SumoEnvironment for the newly selected scenario, so a bare
  // stop() is the correct and sufficient reset here.
  const switchScenario = async () => {
    if (!selectedScenarioId) return;
    setSwitching(true);
    setActionError(null);
    setThroughputHistory([]);
    try {
      if (isRunning) await api.simulation.stop();
      await api.simulation.startScenario(selectedScenarioId);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setActionError(typeof detail === 'object' ? (detail?.reason ?? JSON.stringify(detail)) : (detail ?? 'Failed to start scenario.'));
    }
    setSwitching(false);
    refresh();
  };

  const toggleRun = async () => {
    setActionError(null);
    try {
      if (isRunning) {
        await api.simulation.stop();
      } else if (selectedScenarioId) {
        await api.simulation.startScenario(selectedScenarioId);
      } else {
        await api.simulation.start();
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setActionError(typeof detail === 'object' ? (detail?.reason ?? JSON.stringify(detail)) : (detail ?? 'Action failed.'));
    }
    refresh();
  };

  const stepOnce = async () => {
    try {
      await api.simulation.step(1);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setActionError(typeof detail === 'object' ? (detail?.reason ?? JSON.stringify(detail)) : (detail ?? 'Step failed.'));
    }
    refresh();
  };

  const resetSim = async () => {
    setThroughputHistory([]);
    try {
      await api.simulation.reset();
    } catch {
      /* refresh() reports the resulting state */
    }
    refresh();
  };

  return (
    <section className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Scenario sandbox</h2>
          <p className="text-xs text-slate-500">
            Runs an isolated SUMO inside the API process for scenario what-ifs. It does not drive the corridor map,
            the control service, or emergency corridors.
          </p>
        </div>

        <div className="flex items-center gap-3 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-2">
          <select
            className="border border-slate-200 rounded-lg px-3 py-2 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none min-w-[220px]"
            value={selectedScenarioId}
            onChange={(e) => setSelectedScenarioId(e.target.value)}
            disabled={!scenarios.length}
          >
            {!scenarios.length && <option value="">Scenarios unavailable</option>}
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>{s.id} — {s.name}</option>
            ))}
          </select>
          <button
            className="px-3 py-2 rounded-lg text-sm font-medium bg-sky-100 text-sky-700 hover:bg-sky-200 transition-colors disabled:opacity-50"
            onClick={switchScenario}
            disabled={!selectedScenarioId || switching}
            title="Reset state and start the selected scenario at seed 42"
          >
            {switching ? 'Switching…' : 'Switch Scenario'}
          </button>
          <div className="w-px h-6 bg-slate-200 mx-1"></div>
          <button
            className={clsx(
              "p-2 rounded-lg transition-colors",
              isRunning ? "bg-red-100 text-red-600 hover:bg-red-200" : "bg-emerald-100 text-emerald-600 hover:bg-emerald-200"
            )}
            onClick={toggleRun}
            title={isRunning ? "Stop" : "Start"}
          >
            {isRunning ? <Square className="w-5 h-5" fill="currentColor" /> : <Play className="w-5 h-5" fill="currentColor" />}
          </button>
          <button
            className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            title="Step"
            onClick={stepOnce}
            disabled={!isRunning}
          >
            <FastForward className="w-5 h-5" />
          </button>
          <div className="w-px h-6 bg-slate-200 mx-1"></div>
          <button className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 transition-colors" title="Reset" onClick={resetSim}>
            <RotateCcw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {scenarios.length > 0 && selectedScenarioId && (
        <p className="text-xs text-slate-500 -mt-4">
          {scenarios.find((s) => s.id === selectedScenarioId)?.description}
        </p>
      )}

      {actionError && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <h3 className="text-sm font-bold text-amber-800">Action failed</h3>
          <p className="text-sm text-amber-700 mt-1">{actionError}</p>
        </div>
      )}

      {unavailable && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
          <h3 className="text-sm font-bold text-slate-700">Simulation unavailable</h3>
          <p className="text-sm text-slate-500 mt-1">{unavailable}</p>
        </div>
      )}

      {isStale && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
          <div className="text-sm text-amber-700">
            <p>Sandbox simulation has not advanced for {state?.step_age_s?.toFixed(1)}s.</p>
            {state?.sandbox_fault && <p className="mt-1 text-xs text-amber-600">{state.sandbox_fault}</p>}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5 flex items-center justify-between">
        <div className="flex gap-8">
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Scenario</div>
            <div className="font-mono text-xl font-bold text-slate-900">{state?.scenario_id ?? state?.scenario ?? DASH}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Seed</div>
            <div className="font-mono text-xl font-bold text-slate-900">{fmt(state?.seed)}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Current Step</div>
            <div className="font-mono text-xl font-bold text-slate-900">{isLive ? fmt(state?.step_count ?? state?.step) : DASH}</div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Elapsed Sim Time</div>
            <div className="font-mono text-xl font-bold text-slate-900">
              {isLive ? (state?.simulation_time !== undefined ? `${fmt(state.simulation_time)}s` : (state?.sim_time ?? DASH)) : DASH}
            </div>
          </div>
        </div>
        <div>
          <span className={clsx(
            "px-3 py-1 text-sm font-semibold rounded-full",
            isRunning ? (isStale ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700") : "bg-slate-100 text-slate-700"
          )}>
            {isRunning ? (isStale ? 'Stalled' : 'Running') : 'Stopped'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Car className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Total Vehicles</h3>
            <TelemetrySourceBadge source={isLive ? (metrics?.source ?? null) : null} showIcon={false} />
          </div>
          <div className="text-4xl font-bold text-slate-900 mt-2">{isLive ? fmt(metrics?.total_vehicles) : DASH}</div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Avg Speed</h3>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <div className="text-4xl font-bold text-slate-900">{isLive ? fmt(metrics?.avg_speed, 1) : DASH}</div>
            <div className="text-sm font-medium text-slate-500">km/h</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Clock className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Total Waiting Time</h3>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <div className="text-4xl font-bold text-slate-900">{isLive ? fmt(metrics?.avg_delay, 1) : DASH}</div>
            <div className="text-sm font-medium text-slate-500">s</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <BarChart3 className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Throughput</h3>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <div className="text-4xl font-bold text-slate-900">{isLive ? fmt(metrics?.throughput) : DASH}</div>
            <div className="text-sm font-medium text-slate-500">PCU/hr</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
        <h3 className="text-sm font-semibold text-slate-800 mb-4">Throughput history</h3>
        {!throughputHistory.length && (
          <p className="text-xs text-slate-400 mb-2">
            No samples yet. History accumulates while the sandbox runs.
          </p>
        )}
        <div className="h-[240px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={throughputHistory} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="step" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0' }}
                labelStyle={{ color: '#64748b', fontWeight: 500, marginBottom: '4px' }}
              />
              <Line type="monotone" dataKey="throughput" stroke="#0284c7" strokeWidth={2} dot={false} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}

export default function SimulationPage() {
  return (
    <div className="p-6 space-y-10">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">SUMO Simulation</h1>
        <p className="text-sm text-slate-500">Traffic Scenario Testing Environment</p>
      </div>

      <BridgeObserverPane />

      <hr className="border-slate-200" />

      <ScenarioSandboxPane />
    </div>
  );
}
