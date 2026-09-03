import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { Leaf, Wind, Activity, Map, ArrowUp } from 'lucide-react';

const mockTrendData = [
  { name: 'Jan', before: 120, after: 120 },
  { name: 'Feb', before: 118, after: 110 },
  { name: 'Mar', before: 122, after: 105 },
  { name: 'Apr', before: 130, after: 98 },
  { name: 'May', before: 128, after: 95 },
  { name: 'Jun', before: 135, after: 90 },
  { name: 'Jul', before: 140, after: 88 },
  { name: 'Aug', before: 138, after: 85 },
];

const mockPieData = [
  { name: 'Cars', value: 45 },
  { name: '2W', value: 25 },
  { name: 'Buses', value: 15 },
  { name: 'Trucks', value: 15 },
];

const COLORS = ['#0284c7', '#10b981', '#f59e0b', '#ef4444'];

const topCorridors = [
  { name: 'MG Road', reduction: 35 },
  { name: 'Ring Road Phase 1', reduction: 28 },
  { name: 'Airport Road', reduction: 25 },
  { name: 'Tech Park Avenue', reduction: 22 },
  { name: 'Old Madras Road', reduction: 18 },
];

export default function EmissionsPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col">
        <h1 className="text-2xl font-bold text-slate-900">Emissions Monitoring</h1>
        <p className="text-sm text-slate-500">CO₂ & Pollutant Tracking Dashboard</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Leaf className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Total CO₂ Saved</h3>
          </div>
          <div className="flex items-baseline gap-2">
            <div className="text-4xl font-bold text-slate-900">12.4t</div>
            <div className="flex items-center text-sm font-medium text-emerald-600">
              <ArrowUp className="w-4 h-4 mr-1" />
              18%
            </div>
          </div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mt-2">vs baseline</p>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Wind className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">NOx Reduction</h3>
          </div>
          <div className="flex items-baseline gap-2">
            <div className="text-4xl font-bold text-slate-900">22%</div>
            <div className="text-sm font-medium text-emerald-600">Target: 20%</div>
          </div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mt-2">Monthly Average</p>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Fleet Efficiency</h3>
          </div>
          <div className="flex items-baseline gap-2">
            <div className="text-4xl font-bold text-slate-900">87%</div>
            <div className="flex items-center text-sm font-medium text-emerald-600">
              <ArrowUp className="w-4 h-4 mr-1" />
              Improving
            </div>
          </div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mt-2">Index Score</p>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <div className="flex items-center gap-3 mb-2">
            <Map className="w-5 h-5 text-sky-600" />
            <h3 className="text-sm font-semibold text-slate-800">Green Zone Coverage</h3>
          </div>
          <div className="flex items-baseline gap-2">
            <div className="text-4xl font-bold text-slate-900">34</div>
            <div className="text-sm font-medium text-slate-500">junctions</div>
          </div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mt-2">Active Zones</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-4">Monthly Emissions Trend (CO₂ tons)</h3>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={mockTrendData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorBefore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#94a3b8" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorAfter" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0d9488" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#0d9488" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0' }}
                />
                <Area type="monotone" dataKey="before" name="Before Surakshanet" stroke="#94a3b8" fillOpacity={1} fill="url(#colorBefore)" />
                <Area type="monotone" dataKey="after" name="After Surakshanet" stroke="#0d9488" fillOpacity={1} fill="url(#colorAfter)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-4">Emissions by Vehicle Type</h3>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={mockPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {mockPieData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5">
        <h3 className="text-sm font-semibold text-slate-800 mb-4">Top 5 Corridors by Emission Reduction</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left text-slate-600">
            <thead className="text-xs text-slate-500 uppercase bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-6 py-3 font-medium">Corridor Name</th>
                <th className="px-6 py-3 font-medium w-2/3">Reduction Percentage</th>
                <th className="px-6 py-3 font-medium text-right">%</th>
              </tr>
            </thead>
            <tbody>
              {topCorridors.map((corridor, idx) => (
                <tr key={idx} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-6 py-4 font-medium text-slate-900">{corridor.name}</td>
                  <td className="px-6 py-4">
                    <div className="w-full bg-slate-200 rounded-full h-2.5">
                      <div className="bg-emerald-500 h-2.5 rounded-full" style={{ width: `${corridor.reduction}%` }}></div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right font-bold text-slate-700">{corridor.reduction}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
