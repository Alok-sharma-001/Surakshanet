import { useState } from 'react';
import { 
  TrendingDown, TrendingUp, BarChart3, FileText, 
  Download, Filter, ChevronDown, AlertTriangle 
} from 'lucide-react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer, Legend 
} from 'recharts';
import clsx from 'clsx';

// SN-012g/§13.10: this "Executive Analytics" page previously claimed
// specific figures — "-24% Avg Delay Reduction vs 18% baseline", "+15%
// Throughput Increase", "LOS B+ improved from C" — plus a full
// Baseline-vs-Active weekly bar chart, none backed by any measurement.
// Honest placeholders below instead.
const mockChartData: { name: string; baseline: number; active: number }[] = [];

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState('30d');

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

      {/* Middle Row */}
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
            {/* SN-012g/§13.10: this used to render fixed blur blobs and a
                "CRITICAL NODE" label unconditionally — a specific claim with
                no congestion data behind it. No real per-node congestion
                heatmap source is wired to this page yet. */}
            <div className="flex flex-col items-center gap-2 text-slate-400">
              <AlertTriangle className="w-6 h-6" />
              <span className="text-xs">No congestion data measured yet</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
