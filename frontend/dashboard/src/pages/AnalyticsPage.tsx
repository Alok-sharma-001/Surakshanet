import { useState, useEffect } from 'react';
import { 
  TrendingDown, TrendingUp, BarChart3, FileText, 
  Download, Filter, ChevronDown, AlertTriangle,
  ShieldCheck, Info, CheckCircle2, XCircle, Clock, AlertOctagon
} from 'lucide-react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer, Legend 
} from 'recharts';
import clsx from 'clsx';
import { api } from '../services/api';

// SN-012g/§13.10: this "Executive Analytics" page previously claimed
// specific figures — "-24% Avg Delay Reduction vs 18% baseline", "+15%
// Throughput Increase", "LOS B+ improved from C" — plus a full
// Baseline-vs-Active weekly bar chart, none backed by any measurement.
// Honest placeholders below instead.
const mockChartData: { name: string; baseline: number; active: number }[] = [];

interface FPRateData {
  overall: {
    total_flags: number;
    confirmed: number;
    dismissed: number;
    unverified: number;
    false_positive_rate: number;
  };
  by_flag_type: Record<string, {
    total: number;
    confirmed: number;
    dismissed: number;
    unverified: number;
    false_positive_rate: number;
  }>;
}

interface ModelLimitationItem {
  name: string;
  limitations: string[];
  mitigation?: string;
  declared_tag?: string;
}

interface ModelLimitationsData {
  models: Record<string, ModelLimitationItem>;
  system_bias: string;
}

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState('30d');
  const [fpData, setFpData] = useState<FPRateData | null>(null);
  const [limitationsData, setLimitationsData] = useState<ModelLimitationsData | null>(null);
  const [loadingGov, setLoadingGov] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    async function loadGovernanceData() {
      try {
        const [fpRes, limitRes] = await Promise.all([
          api.vision.getFalsePositiveRate().catch(() => null),
          api.vision.getModelLimitations().catch(() => null),
        ]);
        if (isMounted) {
          if (fpRes?.data) setFpData(fpRes.data);
          if (limitRes?.data) setLimitationsData(limitRes.data);
        }
      } finally {
        if (isMounted) setLoadingGov(false);
      }
    }
    loadGovernanceData();
    return () => { isMounted = false; };
  }, []);

  return (
    <div className="h-full flex flex-col gap-6 p-6 overflow-y-auto">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-syne font-bold text-slate-900">Executive Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">System performance vs Baseline (Q3 2024)</p>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex bg-slate-100 rounded-lg p-1">
            <button 
              onClick={() => setTimeRange('today')}
              className={clsx(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                timeRange === 'today' ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"
              )}
            >
              Today
            </button>
            <button 
              onClick={() => setTimeRange('7d')}
              className={clsx(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                timeRange === '7d' ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"
              )}
            >
              Last 7 Days
            </button>
            <button 
              onClick={() => setTimeRange('30d')}
              className={clsx(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                timeRange === '30d' ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"
              )}
            >
              Last 30 Days
            </button>
          </div>

          <div className="h-6 w-px bg-slate-200"></div>

          <button className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors">
            <Filter className="w-4 h-4" />
            All Corridors
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </button>

          <div className="flex gap-2">
            <button className="p-2 bg-white border border-slate-200 rounded-lg text-slate-500 hover:text-teal-600 hover:border-teal-200 transition-colors" title="Export PDF">
              <FileText className="w-4 h-4" />
            </button>
            <button className="p-2 bg-white border border-slate-200 rounded-lg text-slate-500 hover:text-teal-600 hover:border-teal-200 transition-colors" title="Export CSV">
              <Download className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Top Row - KPI Cards */}
      <div className="grid grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xs font-medium text-slate-500 uppercase tracking-wider">Avg Delay Reduction</h2>
            <div className="w-8 h-8 rounded-full bg-teal-50 flex items-center justify-center">
              <TrendingDown className="w-4 h-4 text-teal-600" />
            </div>
          </div>
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-3xl font-syne font-bold text-slate-300">—</span>
            <span className="text-sm text-slate-500">not measured</span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xs font-medium text-slate-500 uppercase tracking-wider">Throughput Increase</h2>
            <div className="w-8 h-8 rounded-full bg-emerald-50 flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-emerald-600" />
            </div>
          </div>
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-3xl font-syne font-bold text-slate-300">—</span>
            <span className="text-sm text-slate-500">not measured</span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xs font-medium text-slate-500 uppercase tracking-wider">Level of Service (LOS)</h2>
            <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center">
              <BarChart3 className="w-4 h-4 text-slate-600" />
            </div>
          </div>
          <div className="flex items-baseline gap-2 mb-3">
            <span className="text-3xl font-syne font-bold text-slate-300">—</span>
            <span className="text-sm text-slate-500">not measured</span>
          </div>
        </div>
      </div>

      {/* Middle Row - Performance Trends & Heatmap */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-6">Peak-Hour Performance Trends</h2>
          <div className="h-72 relative">
            {mockChartData.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-400 z-10">
                No performance trend data measured yet
              </div>
            )}
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={mockChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} dy={10} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                <Tooltip 
                  cursor={{ fill: '#f8fafc' }}
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', color: '#64748b', paddingTop: '10px' }} />
                <Bar dataKey="baseline" name="Baseline" fill="#94a3b8" radius={[4, 4, 0, 0]} barSize={24} />
                <Bar dataKey="active" name="Surakshanet Active" fill="#0d9488" radius={[4, 4, 0, 0]} barSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="col-span-1 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5 flex flex-col">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-sm font-semibold text-slate-800">Congestion Heatmap</h2>
          </div>
          
          <div className="flex-1 bg-slate-50/70 rounded-xl relative overflow-hidden flex items-center justify-center border border-slate-200 min-h-[180px]">
            <div className="flex flex-col items-center gap-2 text-slate-400">
              <AlertTriangle className="w-6 h-6" />
              <span className="text-xs">No congestion data measured yet</span>
            </div>
          </div>
        </div>
      </div>

      {/* SN-110: False-Positive Rate Tracking Panel */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">Computer Vision False-Positive Tracking (SN-110)</h2>
                <p className="text-xs text-slate-500">Live accountability metrics derived from human operator resolution decisions</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
              Formula: dismissed / total
            </span>
          </div>
        </div>

        {/* Overall Resolution Summary */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block mb-1">Overall FP Rate</span>
            <span className="text-2xl font-bold text-slate-900">
              {fpData ? `${(fpData.overall.false_positive_rate * 100).toFixed(1)}%` : '0.0%'}
            </span>
            <span className="text-[11px] text-slate-400 block mt-1">dismissed vs total</span>
          </div>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider block mb-1">Total Flags</span>
            <span className="text-2xl font-bold text-slate-800">{fpData?.overall.total_flags ?? 0}</span>
            <span className="text-[11px] text-slate-400 block mt-1">all detector flags</span>
          </div>
          <div className="p-4 rounded-xl bg-emerald-50/60 border border-emerald-200">
            <div className="flex items-center gap-1.5 text-emerald-700 mb-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span className="text-xs font-medium uppercase tracking-wider">Confirmed</span>
            </div>
            <span className="text-2xl font-bold text-emerald-800">{fpData?.overall.confirmed ?? 0}</span>
            <span className="text-[11px] text-emerald-600 block mt-1">operator verified</span>
          </div>
          <div className="p-4 rounded-xl bg-amber-50/60 border border-amber-200">
            <div className="flex items-center gap-1.5 text-amber-700 mb-1">
              <XCircle className="w-3.5 h-3.5" />
              <span className="text-xs font-medium uppercase tracking-wider">Dismissed</span>
            </div>
            <span className="text-2xl font-bold text-amber-800">{fpData?.overall.dismissed ?? 0}</span>
            <span className="text-[11px] text-amber-600 block mt-1">false alarms</span>
          </div>
          <div className="p-4 rounded-xl bg-purple-50/60 border border-purple-200">
            <div className="flex items-center gap-1.5 text-purple-700 mb-1">
              <Clock className="w-3.5 h-3.5" />
              <span className="text-xs font-medium uppercase tracking-wider">Unverified</span>
            </div>
            <span className="text-2xl font-bold text-purple-800">{fpData?.overall.unverified ?? 0}</span>
            <span className="text-[11px] text-purple-600 block mt-1">awaiting human gate</span>
          </div>
        </div>

        {/* Per-Flag-Type Breakdown */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border border-slate-200 rounded-lg overflow-hidden">
            <thead className="bg-slate-50 text-slate-600 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-200">
              <tr>
                <th className="px-4 py-3">Suspicion Flag Type</th>
                <th className="px-4 py-3">Total Fired</th>
                <th className="px-4 py-3">Confirmed (True Pos)</th>
                <th className="px-4 py-3">Dismissed (False Pos)</th>
                <th className="px-4 py-3">Pending Gate</th>
                <th className="px-4 py-3">False-Positive Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loadingGov ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                    Loading false-positive metrics...
                  </td>
                </tr>
              ) : fpData?.by_flag_type && Object.keys(fpData.by_flag_type).length > 0 ? (
                Object.entries(fpData.by_flag_type).map(([key, stat]) => (
                  <tr key={key} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3 font-semibold text-slate-800">{key.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-3 text-slate-600">{stat.total}</td>
                    <td className="px-4 py-3 text-emerald-700 font-medium">{stat.confirmed}</td>
                    <td className="px-4 py-3 text-amber-700 font-medium">{stat.dismissed}</td>
                    <td className="px-4 py-3 text-purple-700">{stat.unverified}</td>
                    <td className="px-4 py-3 font-bold text-slate-900">
                      {stat.total > 0 ? `${(stat.false_positive_rate * 100).toFixed(1)}%` : '0.0%'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                    No behavior flags recorded yet. Metrics update dynamically as operators confirm or dismiss incidents.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* SN-110: Model Limitations and Declared Biases Panel */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
        <div className="flex items-center gap-2.5 border-b border-slate-100 pb-4">
          <div className="w-8 h-8 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600">
            <AlertOctagon className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">Model Limitations & Declared Biases (SN-110)</h2>
            <p className="text-xs text-slate-500">
              Transparent publication of architectural constraints per docs/17-security-privacy.md §6
            </p>
          </div>
        </div>

        {/* System Bias Alert Banner */}
        <div className="p-4 rounded-lg bg-amber-50/70 border border-amber-200 text-xs text-amber-900 space-y-1">
          <div className="flex items-center gap-2 font-bold text-amber-950">
            <Info className="w-4 h-4 text-amber-600" />
            Declared System Bias: Heterogeneous Indian Traffic (IRC:106-1990)
          </div>
          <p className="text-amber-800 leading-relaxed pl-6">
            {limitationsData?.system_bias ||
              'Systematic under-counting of two-wheelers and auto-rickshaws biases unweighted density estimators. Addressed via Indian Road Congress (IRC) PCU weighting and mandatory operator verification gates.'}
          </p>
        </div>

        {/* Model Limitations Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border border-slate-200 rounded-lg overflow-hidden">
            <thead className="bg-slate-50 text-slate-600 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-200">
              <tr>
                <th className="px-4 py-3 w-1/4">Model / Pipeline</th>
                <th className="px-4 py-3 w-1/2">Stated Limitations</th>
                <th className="px-4 py-3 w-1/4">Mitigation / Declared Tag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {limitationsData?.models ? (
                Object.entries(limitationsData.models).map(([key, item]) => (
                  <tr key={key} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3 font-semibold text-slate-900 align-top">
                      {item.name}
                    </td>
                    <td className="px-4 py-3 text-slate-700 align-top space-y-1">
                      {item.limitations.map((lim, idx) => (
                        <div key={idx} className="flex items-start gap-1.5">
                          <span className="text-slate-400 mt-0.5">•</span>
                          <span>{lim}</span>
                        </div>
                      ))}
                    </td>
                    <td className="px-4 py-3 text-slate-600 align-top">
                      {item.declared_tag && (
                        <span className="inline-block px-2 py-0.5 rounded font-mono text-[11px] bg-slate-100 text-slate-800 border border-slate-200 mb-1">
                          {item.declared_tag}
                        </span>
                      )}
                      {item.mitigation && (
                        <p className="text-[11px] text-slate-500 italic mt-0.5">{item.mitigation}</p>
                      )}
                      {!item.declared_tag && !item.mitigation && (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3} className="px-4 py-4 text-center text-slate-400">
                    Loading declared model limitations...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
