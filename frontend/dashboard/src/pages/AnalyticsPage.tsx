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

const mockChartData = [
  { name: 'Mon', baseline: 65, active: 82 },
  { name: 'Tue', baseline: 62, active: 85 },
  { name: 'Wed', baseline: 58, active: 80 },
  { name: 'Thu', baseline: 60, active: 84 },
  { name: 'Fri', baseline: 55, active: 78 },
  { name: 'Sat', baseline: 75, active: 90 },
  { name: 'Sun', baseline: 78, active: 92 },
];

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
            <span className="text-3xl font-syne font-bold text-teal-600">-24%</span>
            <span className="text-sm text-slate-500">vs 18% baseline</span>
          </div>
          <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-teal-500 rounded-full" style={{ width: '75%' }}></div>
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
            <span className="text-3xl font-syne font-bold text-teal-600">+15%</span>
            <span className="text-sm text-slate-500">peak hours</span>
          </div>
          <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-emerald-500 rounded-full" style={{ width: '60%' }}></div>
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
            <span className="text-3xl font-syne font-bold text-slate-900">B+</span>
            <span className="text-sm text-slate-500">improved from C</span>
          </div>
          <div className="flex gap-1 h-3 items-end">
            <div className="flex-1 bg-slate-200 rounded-sm h-1/3"></div>
            <div className="flex-1 bg-slate-200 rounded-sm h-1/2"></div>
            <div className="flex-1 bg-slate-200 rounded-sm h-2/3"></div>
            <div className="flex-1 bg-teal-400 rounded-sm h-full"></div>
            <div className="flex-1 bg-teal-500 rounded-sm h-full"></div>
          </div>
        </div>
      </div>

      {/* Middle Row */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-5">
          <h2 className="text-sm font-semibold text-slate-800 mb-6">Peak-Hour Performance Trends</h2>
          <div className="h-72">
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
          
          <div className="flex-1 bg-slate-900 rounded-xl relative overflow-hidden flex items-center justify-center border border-slate-800">
            {/* Heatmap Visual */}
            <div className="absolute w-32 h-32 bg-red-500/40 rounded-full blur-2xl top-4 left-6"></div>
            <div className="absolute w-24 h-24 bg-red-400/50 rounded-full blur-xl top-12 left-16"></div>
            <div className="absolute w-40 h-40 bg-blue-500/30 rounded-full blur-2xl bottom-4 right-4"></div>
            <div className="absolute w-20 h-20 bg-amber-500/40 rounded-full blur-xl top-10 right-10"></div>
            
            <div className="absolute z-10 flex flex-col items-center gap-1 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-white/90">
              <AlertTriangle className="w-6 h-6 text-amber-400 drop-shadow-md" />
              <span className="text-[10px] font-bold tracking-wider">CRITICAL NODE</span>
            </div>
            
            {/* Legend inside map view */}
            <div className="absolute bottom-3 left-3 right-3 bg-white/10 backdrop-blur-sm p-2 rounded-lg border border-white/20">
              <div className="flex justify-between text-[10px] text-white/80 font-medium mb-1">
                <span>Free Flow</span>
                <span>Severe</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-gradient-to-r from-emerald-400 via-amber-400 to-red-500"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
