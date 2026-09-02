import React, { useState } from 'react';
import { Play, Square, Settings } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Card } from '../components/common/Card';

const mockTrainingData = Array.from({ length: 50 }, (_, i) => ({
  episode: i * 10,
  reward: -5000 + Math.log(i + 1) * 2000 + Math.random() * 500,
  epsilon: Math.max(0.01, 1 - i * 0.03),
  marlDelay: 120 - Math.log(i + 1) * 15,
  fixedDelay: 110,
}));

export const SignalControlPage: React.FC = () => {
  const [isTraining, setIsTraining] = useState(false);
  const [controlMode, setControlMode] = useState('MARL');

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Signal Control & MARL</h1>
          <p className="text-gray-500 mt-1">Manage intersection control logic and agent training</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Control Panel */}
        <Card title="Training Control Panel" className="col-span-1">
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Scenario</label>
              <select className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border">
                <option>Morning Peak (08:00 - 11:00)</option>
                <option>Evening Peak (17:00 - 20:00)</option>
                <option>Off-Peak Normal</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Episodes</label>
              <select className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border">
                <option>100 Episodes</option>
                <option>500 Episodes</option>
                <option>1000 Episodes</option>
              </select>
            </div>
            
            <div className="pt-4 border-t border-gray-100 flex gap-3">
              <button 
                onClick={() => setIsTraining(!isTraining)}
                className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-lg font-medium text-white transition-colors ${
                  isTraining ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
                }`}
              >
                {isTraining ? <Square size={18} /> : <Play size={18} />}
                {isTraining ? 'Stop Training' : 'Start Training'}
              </button>
            </div>

            {isTraining && (
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-100 mt-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="font-medium text-blue-900">Training in progress...</span>
                  <span className="text-blue-700">Ep 42/100</span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full w-[42%]" />
                </div>
                <div className="flex justify-between text-xs text-blue-700 mt-2">
                  <span>Reward: -1250.4</span>
                  <span>Epsilon: 0.15</span>
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Global Mode Toggle */}
        <Card title="Global Control Mode" className="col-span-1 lg:col-span-2">
          <div className="flex flex-col h-full justify-center space-y-6 px-4">
            <div className="grid grid-cols-3 gap-4">
              {['MARL', 'WEBSTER', 'MANUAL'].map((mode) => (
                <button
                  key={mode}
                  onClick={() => setControlMode(mode)}
                  className={`py-4 px-6 rounded-xl border-2 font-bold text-center transition-all ${
                    controlMode === mode 
                      ? 'border-blue-500 bg-blue-50 text-blue-700' 
                      : 'border-gray-200 hover:border-gray-300 text-gray-500'
                  }`}
                >
                  <Settings className={`mx-auto mb-2 ${controlMode === mode ? 'text-blue-500' : 'text-gray-400'}`} />
                  {mode}
                </button>
              ))}
            </div>
            <p className="text-sm text-gray-500 text-center">
              {controlMode === 'MARL' && 'Multi-Agent Reinforcement Learning is dynamically controlling all connected junctions.'}
              {controlMode === 'WEBSTER' && 'Fallback to Webster method: fixed timing based on historical flow data.'}
              {controlMode === 'MANUAL' && 'Manual override active. Operators must set phases directly.'}
            </p>
          </div>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Cumulative Reward over Episodes" className="h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={mockTrainingData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="episode" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="reward" stroke="#8b5cf6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Avg Delay: MARL vs Fixed" className="h-[350px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={mockTrainingData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="episode" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" name="MARL Delay (s)" dataKey="marlDelay" stroke="#10b981" strokeWidth={2} dot={false} />
              <Line type="monotone" name="Fixed Timer (s)" dataKey="fixedDelay" stroke="#f43f5e" strokeWidth={2} strokeDasharray="5 5" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
};

export default SignalControlPage;
