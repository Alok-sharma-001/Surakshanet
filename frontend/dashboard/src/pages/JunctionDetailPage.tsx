import React from 'react';
import { ArrowLeft, Clock, Activity, Settings } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Card } from '../../components/common/Card';
import { StatusBadge } from '../../components/common/StatusBadge';
import { useNavigate, useParams } from 'react-router-dom';

const mockChartData = Array.from({ length: 30 }, (_, i) => ({
  time: `-${30 - i}m`,
  pcu: Math.floor(Math.random() * 500) + 1000,
}));

const mockPieData = [
  { name: 'Cars', value: 400 },
  { name: 'Motorcycles', value: 300 },
  { name: 'Buses', value: 50 },
  { name: 'Trucks', value: 100 },
];
const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

export const JunctionDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams();

  const renderQuadrant = (dir: string, pcu: number, queue: number, speed: number, color: string) => (
    <div className={`p-4 rounded-xl border ${color} bg-white flex flex-col`}>
      <h4 className="font-bold text-gray-700 mb-2">{dir} Approach</h4>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-500">PCU</p>
          <p className="font-semibold text-lg">{pcu}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Avg Speed</p>
          <p className="font-semibold text-lg">{speed} km/h</p>
        </div>
      </div>
      <div className="mt-3">
        <p className="text-xs text-gray-500 mb-1">Queue Length</p>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div className="bg-red-500 h-2 rounded-full" style={{ width: `${Math.min(queue / 200 * 100, 100)}%` }} />
        </div>
        <p className="text-xs text-right text-gray-500 mt-1">{queue}m</p>
      </div>
    </div>
  );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <button onClick={() => navigate(-1)} className="flex items-center text-blue-600 hover:text-blue-800 mb-6 font-medium">
        <ArrowLeft size={20} className="mr-2" /> Back to Map
      </button>

      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Phool Bagh Junction</h1>
          <p className="text-gray-500 mt-1">ID: {id || 'j1'} • Lat: 26.2124, Lng: 78.1772</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status="MARL Active" variant="success" />
          <StatusBadge status="LOS C" variant="warning" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Signal Status */}
        <Card title="Signal Status" className="col-span-1" bodyClassName="flex flex-col items-center justify-center py-8">
          <div className="w-24 bg-gray-900 rounded-3xl p-4 flex flex-col gap-4 items-center shadow-inner">
            <div className="w-12 h-12 rounded-full bg-red-900 opacity-30 shadow-[inset_0_2px_4px_rgba(0,0,0,0.4)]" />
            <div className="w-12 h-12 rounded-full bg-yellow-900 opacity-30 shadow-[inset_0_2px_4px_rgba(0,0,0,0.4)]" />
            <div className="w-12 h-12 rounded-full bg-green-500 shadow-[0_0_20px_#22c55e]" />
          </div>
          <div className="mt-8 text-center">
            <p className="text-sm text-gray-500 font-medium">Current Phase</p>
            <p className="text-2xl font-bold text-gray-900">North-South Straight</p>
          </div>
          <div className="mt-6 flex justify-between w-full px-4 text-sm font-medium">
            <div className="text-center">
              <span className="block text-gray-400">Elapsed</span>
              <span className="text-blue-600 text-lg">24s</span>
            </div>
            <div className="text-center">
              <span className="block text-gray-400">Remaining</span>
              <span className="text-green-600 text-lg">16s</span>
            </div>
          </div>
        </Card>

        {/* 4 Quadrants */}
        <Card title="Approach Telemetry" className="col-span-1 lg:col-span-2">
          <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg">
            {renderQuadrant('North', 450, 120, 15, 'border-red-200')}
            {renderQuadrant('East', 210, 45, 32, 'border-green-200')}
            {renderQuadrant('West', 320, 80, 22, 'border-yellow-200')}
            {renderQuadrant('South', 510, 150, 12, 'border-red-200')}
          </div>
        </Card>

        {/* Charts */}
        <Card title="Traffic Volume (Last 30m)" className="col-span-1 lg:col-span-2 h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={mockChartData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="time" axisLine={false} tickLine={false} />
              <YAxis axisLine={false} tickLine={false} />
              <Tooltip />
              <Line type="monotone" dataKey="pcu" stroke="#3b82f6" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Vehicle Breakdown" className="col-span-1 h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={mockPieData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                {mockPieData.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap justify-center gap-3 mt-[-20px]">
            {mockPieData.map((entry, index) => (
              <div key={entry.name} className="flex items-center gap-1 text-xs text-gray-600">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index] }} />
                {entry.name}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default JunctionDetailPage;
