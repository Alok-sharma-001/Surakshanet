import React, { useState } from 'react';
import { MapPin, Navigation, Clock } from 'lucide-react';
import { Card } from '../components/common/Card';
import { StatusBadge } from '../components/common/StatusBadge';

export const RoutingPage: React.FC = () => {
  const [calculating, setCalculating] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const handleRoute = () => {
    setCalculating(true);
    setTimeout(() => {
      setCalculating(false);
      setShowResults(true);
    }, 1000);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto h-[calc(100vh-4rem)] flex flex-col">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Dynamic Routing</h1>

      <div className="flex gap-6 h-full min-h-0">
        {/* Sidebar */}
        <div className="w-[400px] flex flex-col gap-6 overflow-y-auto pr-2">
          <Card title="Find Route">
            <div className="space-y-4 relative">
              <div className="absolute left-[11px] top-[30px] bottom-[30px] w-0.5 bg-gray-200" />
              <div className="relative">
                <MapPin className="absolute left-0 top-2 text-green-500" size={24} />
                <input 
                  type="text" 
                  placeholder="Origin Junction"
                  defaultValue="Station Road Junction"
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="relative">
                <MapPin className="absolute left-0 top-2 text-red-500" size={24} />
                <input 
                  type="text" 
                  placeholder="Destination Junction"
                  defaultValue="University Crossing"
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <button 
                onClick={handleRoute}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg flex items-center justify-center gap-2 transition-colors"
              >
                {calculating ? 'Calculating...' : <><Navigation size={18} /> Find Optimal Route</>}
              </button>
            </div>
          </Card>

          {showResults && (
            <Card title="Alternative Routes" className="flex-1">
              <div className="space-y-4">
                {[
                  { id: 1, name: 'Via MG Road', eta: '12 min', dist: '4.2 km', status: 'Optimal', color: 'border-green-500', bg: 'bg-green-50' },
                  { id: 2, name: 'Via City Center', eta: '18 min', dist: '3.8 km', status: 'Congested', color: 'border-red-500', bg: 'bg-white' },
                  { id: 3, name: 'Via Ring Road', eta: '15 min', dist: '5.5 km', status: 'Clear', color: 'border-gray-200', bg: 'bg-white' },
                ].map((r) => (
                  <div key={r.id} className={`p-4 rounded-xl border-2 ${r.color} ${r.bg} cursor-pointer hover:shadow-md transition-shadow`}>
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-bold text-gray-800">{r.name}</h4>
                      {r.id === 1 && <StatusBadge status="Recommended" variant="success" />}
                    </div>
                    <div className="flex gap-4 text-sm text-gray-600">
                      <div className="flex items-center gap-1"><Clock size={14} /> {r.eta}</div>
                      <div className="flex items-center gap-1"><Navigation size={14} /> {r.dist}</div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Map Area */}
        <div className="flex-1 bg-slate-100 rounded-xl border border-gray-200 relative overflow-hidden flex items-center justify-center">
          {!showResults ? (
            <p className="text-gray-400 font-medium">Enter origin and destination to view routes</p>
          ) : (
            <div className="absolute inset-0 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:20px_20px]">
              {/* Mock Route Lines */}
              <svg className="absolute inset-0 w-full h-full">
                <path d="M100,300 C200,200 400,250 600,100" fill="none" stroke="#22c55e" strokeWidth="6" strokeLinecap="round" className="animate-pulse" />
                <path d="M100,300 C200,350 400,350 600,100" fill="none" stroke="#ef4444" strokeWidth="4" strokeDasharray="5 5" />
              </svg>
              {/* Mock Nodes */}
              <div className="absolute top-[300px] left-[100px] w-4 h-4 bg-white border-4 border-green-600 rounded-full transform -translate-x-1/2 -translate-y-1/2" />
              <div className="absolute top-[100px] left-[600px] w-4 h-4 bg-white border-4 border-red-600 rounded-full transform -translate-x-1/2 -translate-y-1/2" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RoutingPage;
