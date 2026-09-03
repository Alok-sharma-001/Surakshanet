import { useState } from 'react';
import { Play, Square, FastForward, RotateCcw, Activity, Clock, Car, BarChart3 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import clsx from 'clsx';

const mockChartData = Array.from({ length: 20 }).map((_, i) => ({
  step: 3900 + i * 10,
  throughput: 800 + Math.random() * 200 - 100
}));

export default function SimulationPage() {
  const [isRunning, setIsRunning] = useState(true);
  const [speed, setSpeed] = useState('1x');

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">SUMO Simulation</h1>
          <p className="text-sm text-slate-500">Traffic Scenario Testing Environment</p>
        </div>
        
        <div className="flex items-center gap-3 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-2">
          <select className="border border-slate-200 rounded-lg px-3 py-2 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none">
            <option>Peak Hour</option>
            <option>Off-Peak</option>
            <option>Emergency</option>
            <option>Festival</option>
          </select>
          <div className="w-px h-6 bg-slate-200 mx-1"></div>
          <button 
            className={clsx(
              "p-2 rounded-lg transition-colors",
              isRunning ? "bg-red-100 text-red-600 hover:bg-red-200" : "bg-emerald-100 text-emerald-600 hover:bg-emerald-200"
            )}
            onClick={() => setIsRunning(!isRunning)}
            title={isRunning ? "Stop" : "Start"}
          >
            {isRunning ? <Square className="w-5 h-5" fill="currentColor" /> : <Play className="w-5 h-5" fill="currentColor" />}
          </button>
          <button className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 transition-colors" title="Step">
            <FastForward className="w-5 h-5" />
          </button>
          <select 
            className="border-none rounded-lg px-2 py-1 bg-slate-50 text-sm font-medium focus:ring-0 outline-none w-16"
            value={speed}
            onChange={(e) => setSpeed(e.target.value)}
          >
            <option value="1x">1x</option>
            <option value="2x">2x</option>
            <option value="5x">5x</option>
            <option value="10x">10x</option>
          </select>
          <div className="w-px h-6 bg-slate-200 mx-1"></div>
          <button className="p-2 rounded-lg text-slate-600 hover:bg-slate-100 transition-colors" title="Reset">
            <RotateCcw className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5 flex items-center justify-between">
        <div className="flex gap-8">
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Current Step</div>
            <div className="font-mono text-xl font-bold text-slate-900">4,092</div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Sim Time</div>
            <div className="font-mono text-xl font-bold text-slate-900">01:08:12</div>
          </div>
        </div>
        <div>
          <span className={clsx(
            "px-3 py-1 text-sm font-semibold rounded-full",
            isRunning ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"
          )}>
            {isRunning ? 'Running' : 'Stopped'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Car className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Total Vehicles</h3>
          </div>
          <div className="text-4xl font-bold text-slate-900 mt-2">1,247</div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Avg Speed</h3>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <div className="text-4xl font-bold text-slate-900">28.5</div>
            <div className="text-sm font-medium text-slate-500">km/h</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Clock className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Total Waiting Time</h3>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <div className="text-4xl font-bold text-slate-900">4,521</div>
            <div className="text-sm font-medium text-slate-500">s</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <BarChart3 className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Throughput</h3>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <div className="text-4xl font-bold text-slate-900">892</div>
            <div className="text-sm font-medium text-slate-500">PCU/hr</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
        <h3 className="text-sm font-semibold text-slate-800 mb-4">Real-time Throughput (last 100 steps)</h3>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={mockChartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
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
    </div>
  );
}
