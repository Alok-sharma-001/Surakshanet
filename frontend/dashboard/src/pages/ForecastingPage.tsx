import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Card } from '../../components/common/Card';

const mockForecastData = Array.from({ length: 24 }, (_, i) => {
  const isFuture = i > 12;
  const base = 1000 + Math.sin(i / 3) * 500;
  return {
    time: `${(8 + Math.floor(i/4)).toString().padStart(2, '0')}:${((i%4)*15).toString().padStart(2, '0')}`,
    actual: isFuture ? null : base + Math.random() * 100,
    forecast15: isFuture && i <= 16 ? base + Math.random() * 50 : null,
    forecast30: isFuture && i > 12 && i <= 20 ? base + Math.random() * 150 : null,
    forecast60: isFuture ? base + Math.random() * 250 : null,
  };
});

export const ForecastingPage: React.FC = () => {
  const kSpill = 0.72;
  
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Traffic Forecasting</h1>
          <p className="text-gray-500 mt-1">Spatio-temporal predictions via GNNs</p>
        </div>
        <select className="border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border bg-white min-w-[250px]">
          <option>All Junctions Aggregate</option>
          <option>Phool Bagh Junction</option>
          <option>City Center Junction</option>
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Chart */}
        <Card title="Multi-Horizon PCU Forecast" className="lg:col-span-3 h-[450px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={mockForecastData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Area type="monotone" dataKey="actual" name="Actual Demand" stroke="#3b82f6" fillOpacity={0.1} fill="#3b82f6" strokeWidth={2} />
              <Area type="monotone" dataKey="forecast15" name="15m Forecast" stroke="#10b981" fill="none" strokeWidth={2} strokeDasharray="5 5" />
              <Area type="monotone" dataKey="forecast30" name="30m Forecast" stroke="#f59e0b" fill="none" strokeWidth={2} strokeDasharray="5 5" />
              <Area type="monotone" dataKey="forecast60" name="60m Forecast" stroke="#ef4444" fill="none" strokeWidth={2} strokeDasharray="5 5" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <div className="space-y-6 lg:col-span-1">
          {/* Spillback */}
          <Card title="Spillback Risk (K_spill)">
            <div className="flex flex-col items-center py-4">
              <div className="relative w-32 h-32 rounded-full flex items-center justify-center border-8 border-yellow-400">
                <span className="text-3xl font-bold text-gray-800">{kSpill}</span>
              </div>
              <p className="mt-4 text-xl font-semibold text-yellow-600">WARNING</p>
              <p className="text-sm text-center text-gray-500 mt-2">Moderate risk of queue spillover to adjacent junctions in the next 15m.</p>
            </div>
          </Card>

          {/* Metrics */}
          <Card title="Model Accuracy">
            <div className="space-y-4">
              <div className="flex justify-between items-center border-b pb-2">
                <span className="text-sm font-medium text-gray-600">15m MAPE</span>
                <span className="font-bold text-green-600">4.2%</span>
              </div>
              <div className="flex justify-between items-center border-b pb-2">
                <span className="text-sm font-medium text-gray-600">30m MAPE</span>
                <span className="font-bold text-yellow-600">8.7%</span>
              </div>
              <div className="flex justify-between items-center pb-2">
                <span className="text-sm font-medium text-gray-600">60m MAPE</span>
                <span className="font-bold text-red-500">14.1%</span>
              </div>
              <button className="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded text-sm font-medium transition-colors">
                Retrain Model
              </button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ForecastingPage;
