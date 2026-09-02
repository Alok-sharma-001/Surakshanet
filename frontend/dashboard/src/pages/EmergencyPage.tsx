import React, { useState } from 'react';
import { Siren, ShieldAlert, CheckCircle, Activity, HeartPulse } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { StatusBadge } from '../../components/common/StatusBadge';

export const EmergencyPage: React.FC = () => {
  const [active, setActive] = useState(false);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Emergency & Priority</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Activate Green Wave" className="col-span-1 border-red-200">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Vehicle Type</label>
              <select className="w-full border-gray-300 rounded-md shadow-sm focus:border-red-500 focus:ring-red-500 p-2 border">
                <option>🚑 Ambulance</option>
                <option>🚒 Fire Engine</option>
                <option>🚓 Police</option>
                <option>⭐ VIP Convoy</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Corridor Selection</label>
              <div className="border border-gray-200 rounded-md p-2 space-y-2 max-h-40 overflow-y-auto bg-gray-50">
                {['MG Road Corridor', 'Station to Hospital', 'Ring Road Outer'].map(c => (
                  <label key={c} className="flex items-center gap-2 text-sm p-1">
                    <input type="radio" name="corridor" className="text-red-600" />
                    {c}
                  </label>
                ))}
              </div>
            </div>
            <button 
              onClick={() => setActive(!active)}
              className={`w-full py-4 rounded-xl font-bold text-white text-lg flex items-center justify-center gap-2 shadow-lg transition-all ${
                active ? 'bg-gray-800 hover:bg-gray-900' : 'bg-red-600 hover:bg-red-700 animate-pulse'
              }`}
            >
              {active ? 'Deactivate Emergency' : <><Siren size={24} /> ACTIVATE GREEN WAVE</>}
            </button>
          </div>
        </Card>

        <Card title="Active Emergency Routes" className="col-span-1 lg:col-span-2">
          {active ? (
            <div className="p-4 rounded-lg border border-red-200 bg-red-50/50">
              <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-red-100 rounded-full text-red-600 animate-bounce"><HeartPulse size={24} /></div>
                  <div>
                    <h3 className="font-bold text-red-900">AMB-7742 (Critical)</h3>
                    <p className="text-sm text-red-700">Station to Hospital Corridor</p>
                  </div>
                </div>
                <StatusBadge status="ACTIVE" variant="error" />
              </div>
              
              <div className="relative mt-8 mb-4">
                <div className="absolute top-1/2 left-4 right-4 h-1 bg-gray-300 -translate-y-1/2" />
                <div className="absolute top-1/2 left-4 right-1/2 h-1 bg-green-500 -translate-y-1/2" />
                <div className="flex justify-between relative z-10 px-4">
                  {[
                    { n: 'Station', s: 'cleared' },
                    { n: 'Phool Bagh', s: 'active' },
                    { n: 'University', s: 'pending' },
                    { n: 'Hospital', s: 'pending' }
                  ].map((j, i) => (
                    <div key={i} className="flex flex-col items-center">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 ${
                        j.s === 'cleared' ? 'bg-green-100 border-green-500 text-green-600' : 
                        j.s === 'active' ? 'bg-white border-blue-500 text-blue-600 shadow-[0_0_15px_rgba(59,130,246,0.5)]' : 
                        'bg-white border-gray-300 text-gray-400'
                      }`}>
                        {j.s === 'cleared' ? <CheckCircle size={16} /> : <Activity size={16} />}
                      </div>
                      <span className="text-xs font-medium mt-1 text-gray-600">{j.n}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-gray-400 py-12">
              <ShieldAlert size={48} className="mb-4 opacity-50" />
              <p>No active emergencies</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default EmergencyPage;
