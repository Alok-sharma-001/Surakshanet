import { useState, useEffect } from 'react';
import { TrendingUp, AlertCircle, BarChart3, RefreshCw } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { clsx } from 'clsx';
import { api } from '../services/api';
import { useTrafficStore } from '../store/trafficStore';
import { TelemetrySourceBadge } from '../components/TelemetrySourceBadge';

export default function ForecastingPage() {
  const storeJunctions = useTrafficStore((state) => state.junctions);
  const [selectedJunctionId, setSelectedJunctionId] = useState<string>('DEL-CP-01');
  const [horizon, setHorizon] = useState<'15' | '30' | '60'>('15');
  const [acknowledged, setAcknowledged] = useState(false);
  const [loading, setLoading] = useState(false);
  // Nothing is known until the API answers. These previously carried a seeded
  // risk of 0.44 and a full seven-point curve, which rendered as a real
  // forecast before any request had been made and persisted when one failed.
  const [spillbackRisk, setSpillbackRisk] = useState<number | null>(null);
  const [forecastSource, setForecastSource] = useState<string | null>(null);
  const [trainingData, setTrainingData] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [unavailableReason, setUnavailableReason] = useState<string | null>(null);
  const [predictionData, setPredictionData] = useState<any[]>([]);

  useEffect(() => {
    if (storeJunctions.length > 0 && selectedJunctionId === 'DEL-CP-01') {
      setSelectedJunctionId(storeJunctions[0].id);
    }
  }, [storeJunctions]);

  const fetchForecast = async () => {
    if (!selectedJunctionId) return;
    setLoading(true);
    try {
      const res = await api.ml.predict(selectedJunctionId);
      const data = res.data;
      if (data && data.spillback_risk !== undefined) {
        setSpillbackRisk(data.spillback_risk);
        setForecastSource(data.source || 'heuristic');
        setTrainingData(data.training_data || null);

        const p15Obj = data.predictions?.find((p: any) => p.minutes === 15);
        setConfidence(p15Obj?.confidence ?? null);
        setUnavailableReason(null);

        // Only the horizons the API actually returned. The `actual` series was
        // previously manufactured from the forecast itself — T-45 rendered as
        // `p15 * 0.75` and plotted as measured history, so the chart's past was
        // derived from its own future. Real history needs a readings query.
        setPredictionData(
          (data.predictions ?? []).map((pt: any) => ({
            name: `T+${pt.minutes}`,
            predicted: pt.predicted_pcu,
          }))
        );
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setUnavailableReason(
        typeof detail === 'object' && detail?.reason
          ? detail.reason
          : 'Forecast unavailable for this junction.'
      );
      setSpillbackRisk(null);
      setForecastSource(null);
      setTrainingData(null);
      setConfidence(null);
      setPredictionData([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecast();
  }, [selectedJunctionId, horizon]);

  const selectedName = storeJunctions.find(j => j.id === selectedJunctionId)?.name ?? null;

  return (
    <div className="space-y-6 animate-in fade-in duration-500 p-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-syne font-bold text-slate-900">Traffic Forecasting</h1>
            <TelemetrySourceBadge source={forecastSource} />
            {trainingData && (
              <span className="text-[10px] font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5 rounded-md uppercase tracking-wider">
                DATA: {trainingData.toUpperCase()}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 mt-1">
            {forecastSource === 'model'
              ? 'Spillback Prediction & Flow Telemetry Model (LSTM + XGBoost)'
              : forecastSource === 'heuristic'
              ? 'Persistence baseline from the latest measured readings (estimated)'
              : 'No forecast loaded'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Junction Selector */}
          <select
            value={selectedJunctionId}
            onChange={(e) => setSelectedJunctionId(e.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-2 bg-white text-sm font-semibold text-slate-700 shadow-sm focus:ring-2 focus:ring-teal-500 outline-none"
          >
            {storeJunctions.map((j) => (
              <option key={j.id} value={j.id}>{j.name}</option>
            ))}
            {!storeJunctions.length && <option value="DEL-CP-01">Connaught Place Outer Circle</option>}
          </select>

          {/* Horizon Pills */}
          <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
            {(['15', '30', '60'] as const).map(h => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={clsx(
                  "px-3 py-1.5 rounded-md text-sm font-semibold transition-all",
                  horizon === h ? "bg-white text-teal-700 outline outline-2 outline-teal-500 shadow-sm z-10" : "text-slate-600 hover:text-slate-900"
                )}
              >
                {h}m
              </button>
            ))}
          </div>

          <button
            onClick={fetchForecast}
            className="p-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-500 shadow-sm"
            title="Refresh Forecast"
          >
            <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin text-teal-600")} />
          </button>
        </div>
      </div>

      {/* Alert Banner for High Spillback Risk */}
      {spillbackRisk !== null && spillbackRisk > 0.70 && !acknowledged && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start justify-between shadow-sm">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-bold text-amber-800">
                High Spillback Risk Detected{selectedName ? ` - ${selectedName}` : ''}
              </h3>
              <p className="text-sm text-amber-700 mt-1">
                Predicted queue exceeds 75% capacity within the next {horizon}-minute horizon. Spillback index: {((spillbackRisk ?? 0) * 100).toFixed(0)}%.
              </p>
            </div>
          </div>
          <button 
            onClick={() => setAcknowledged(true)}
            className="px-4 py-1.5 bg-red-100 text-red-600 hover:bg-red-200 rounded-full text-xs font-bold transition-colors flex-shrink-0"
          >
            Acknowledge
          </button>
        </div>
      )}

      {unavailableReason && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-slate-400 mt-0.5 flex-shrink-0" />
          <div>
            <h3 className="text-sm font-bold text-slate-700">Forecast unavailable</h3>
            <p className="text-sm text-slate-500 mt-1">{unavailableReason}</p>
          </div>
        </div>
      )}

      {/* Main Content (2-column grid) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left: Actual vs Predicted PCU chart card */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 h-[420px] flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center">
              <TrendingUp className="w-4 h-4 mr-2 text-teal-600" />
              Predicted PCU Flow{selectedName ? ` — ${selectedName}` : ''}
            </h3>
            <span className="text-xs font-mono font-bold text-teal-600 bg-teal-50 px-2.5 py-1 rounded">
              Horizon: {horizon} Mins
            </span>
          </div>
          <div className="flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={predictionData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0d9488" stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="#0d9488" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Legend iconType="circle" />
                <Area type="monotone" dataKey="actual" name="Actual (PCU)" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorActual)" />
                <Area type="monotone" dataKey="predicted" name="Predicted (PCU)" stroke="#0d9488" strokeWidth={2} strokeDasharray="5 5" fillOpacity={1} fill="url(#colorPredicted)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Spillback Risk (Kspill) gauge */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex flex-col justify-between items-center text-center">
          <div className="w-full text-left">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center">
              <BarChart3 className="w-4 h-4 mr-2 text-teal-600" />
              Spillback Risk Gauge (Kspill)
            </h3>
          </div>

          <div className="relative w-48 h-28 my-4 flex items-center justify-center">
            {/* Semicircle SVG Gauge */}
            <svg viewBox="0 0 100 50" className="w-full h-full">
              <defs>
                <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#10b981" />
                  <stop offset="65%" stopColor="#f59e0b" />
                  <stop offset="100%" stopColor="#ef4444" />
                </linearGradient>
              </defs>
              <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#e2e8f0" strokeWidth="8" strokeLinecap="round" />
              <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="url(#gaugeGrad)" strokeWidth="8" strokeDasharray="125.6" strokeDashoffset={125.6 * (1 - (spillbackRisk ?? 0))} strokeLinecap="round" />
            </svg>

            <div className="absolute bottom-1 text-center">
              {spillbackRisk === null ? (
                <>
                  <div className="text-2xl font-bold font-mono text-slate-300">—</div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    No Forecast
                  </div>
                </>
              ) : (
                <>
                  <div className="text-2xl font-bold font-mono text-slate-900">{spillbackRisk.toFixed(2)}</div>
                  <div className={clsx(
                    "text-[10px] font-bold uppercase tracking-wider",
                    spillbackRisk < 0.5 ? "text-emerald-600" : spillbackRisk < 0.75 ? "text-amber-600" : "text-red-600"
                  )}>
                    {spillbackRisk < 0.5 ? "Nominal Flow" : spillbackRisk < 0.75 ? "Moderate Spillback" : "Critical Spillback"}
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="w-full space-y-2 text-xs">
            <div className="flex justify-between p-2 rounded bg-slate-50 border border-slate-100">
              <span className="text-slate-500">Capacity Threshold</span>
              <span className="font-bold text-slate-700 font-mono">0.75 Limit</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-slate-50 border border-slate-100">
              <span className="text-slate-500">Model Confidence</span>
              {confidence !== null && forecastSource === 'model' ? (
                <span className="font-bold text-emerald-600 font-mono">{(confidence * 100).toFixed(0)}%</span>
              ) : (
                <span className="font-semibold text-amber-600 text-xs">N/A (Heuristic Fallback)</span>
              )}
            </div>
          </div>
        </div>

      </div>

      {/* The ensemble weight split (55/35/10) and the MAPE figures
          (4.2%, 7.8%, 11.4% with "↓ 0.5% vs avg" and "↑ 1.2% Drift") were
          fixed values presented as validation results. No validation run
          produced them. Restore this section when SN-034 reports real
          per-horizon errors. */}
    </div>
  );
}
