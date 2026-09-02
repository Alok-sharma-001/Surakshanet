import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { Card } from '../components/common/Card';

const mockData = Array.from({ length: 7 }, (_, i) => ({
  day: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i],
  delay: 45 + Math.random() * 20,
  throughput: 3000 + Math.random() * 1000,
}));

export const AnalyticsPage: React.FC = () => {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Analytics & Reports</h1>
        <select className="border border-gray-300 rounded-lg px-3 py-2 bg-white font-medium">
          <option>Last 7 Days</option>
          <option>Last 30 Days</option>
          <option>This Month</option>
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Avg Delay', value: '42.5s', change: '-12%', good: true },
          { label: 'Throughput', value: '4,120/hr', change: '+8%', good: true },
          { label: 'Network LOS', value: 'B+', change: 'Improved', good: true },
          { label: 'Est. Emission Reduction', value: '14.2%', change: '+2.1%', good: true },
        ].map(k => (
          <Card key={k.label} className="!p-5">
            <p className="text-sm text-gray-500 font-medium mb-1">{k.label}</p>
            <p className="text-3xl font-bold text-gray-900">{k.value}</p>
            <p className={`text-sm mt-2 font-medium ${k.good ? 'text-green-600' : 'text-red-500'}`}>
              {k.change} vs prev. period
            </p>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Average Delay by Day" className="h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={mockData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip cursor={{fill: '#f1f5f9'}} />
              <Bar dataKey="delay" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Throughput Trend" className="h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={mockData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="throughput" stroke="#10b981" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="MARL vs Fixed Timer Performance">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Metric</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fixed Timer</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">MARL</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Improvement</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              <tr>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Avg Delay (s)</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">65.2</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-bold">42.5</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-green-600 font-bold">-34.8%</td>
              </tr>
              <tr>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Throughput (PCU/hr)</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">3,250</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-bold">4,120</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-green-600 font-bold">+26.7%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default AnalyticsPage;
