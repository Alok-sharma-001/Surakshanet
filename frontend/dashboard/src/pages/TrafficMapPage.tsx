import React, { useState, useEffect } from 'react';
import { Play, Square, SkipForward, Activity, Car, Clock } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { StatusBadge } from '../../components/common/StatusBadge';
import { useNavigate } from 'react-router-dom';

// Mocks since stores aren't defined in this exercise
const mockJunctions = [
  { id: 'j1', name: 'Phool Bagh Junction', pcu: 1250, phase: 'green', lat: 30, lng: 30, status: 'LOS C' },
  { id: 'j2', name: 'City Center Junction', pcu: 2100, phase: 'red', lat: 70, lng: 40, status: 'LOS E' },
  { id: 'j3', name: 'Station Road Junction', pcu: 800, phase: 'yellow', lat: 45, lng: 80, status: 'LOS B' },
  { id: 'j4', name: 'University Crossing', pcu: 1600, phase: 'green', lat: 80, lng: 75, status: 'LOS D' },
];

export const TrafficMapPage: React.FC = () => {
  const navigate = useNavigate();
  const [simulationActive, setSimulationActive] = useState(false);
  const [simTime, setSimTime] = useState('08:00:00');

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (simulationActive) {
      timer = setInterval(() => {
        setSimTime(prev => {
          const [h, m, s] = prev.split(':').map(Number);
          const date = new Date();
          date.setHours(h, m, s + 1);
          return date.toTimeString().split(' ')[0];
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [simulationActive]);

  return (
    <div className="flex h-[calc(100vh-4rem)] w-full">
      {/* Map Container */}
      <div className="flex-grow relative bg-slate-100 overflow-hidden" id="map">
        <div className="absolute inset-0 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:20px_20px]">
          {mockJunctions.map((j) => (
            <div 
              key={j.id}
              onClick={() => navigate(`/junctions/${j.id}`)}
              className="absolute cursor-pointer transform -translate-x-1/2 -translate-y-1/2 group"
              style={{ top: `${j.lat}%`, left: `${j.lng}%` }}
            >
              <div className={`w-8 h-8 rounded-full border-4 border-white shadow-lg flex items-center justify-center
                ${j.status.includes('A') || j.status.includes('B') ? 'bg-green-500' : 
                  j.status.includes('C') || j.status.includes('D') ? 'bg-yellow-500' : 'bg-red-500'}
              `}>
                <div className={`w-2 h-2 rounded-full ${j.phase === 'green' ? 'bg-green-300' : j.phase === 'red' ? 'bg-red-300' : 'bg-yellow-300'}`} />
              </div>
              <div className="hidden group-hover:block absolute top-10 left-1/2 -translate-x-1/2 bg-white px-3 py-2 rounded shadow-xl text-xs whitespace-nowrap z-10 w-48">
                <p className="font-bold text-gray-800">{j.name}</p>
                <div className="flex justify-between mt-1">
                  <span className="text-gray-500">PCU: {j.pcu}</span>
                  <span className="text-gray-500">Phase: {j.phase.toUpperCase()}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="absolute top-4 left-4 bg-white/90 backdrop-blur px-4 py-2 rounded-lg shadow-sm font-mono text-lg font-semibold flex items-center gap-2">
          <Clock size={20} className="text-blue-600" />
          {simTime}
        </div>
      </div>

      {/* Side Panel */}
      <div className="w-[400px] bg-white border-l border-gray-200 flex flex-col h-full overflow-y-auto">
        <div className="p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-6">Traffic Overview</h2>
          
          <div className="grid grid-cols-2 gap-4 mb-8">
            <Card className="!p-4 bg-blue-50 border-blue-100">
              <div className="flex items-center gap-2 text-blue-600 mb-1">
                <Car size={16} />
                <span className="text-sm font-medium">Total Vehicles</span>
              </div>
              <div className="text-2xl font-bold text-blue-900">4,550</div>
            </Card>
            <Card className="!p-4 bg-green-50 border-green-100">
              <div className="flex items-center gap-2 text-green-600 mb-1">
                <Activity size={16} />
                <span className="text-sm font-medium">Avg Speed</span>
              </div>
              <div className="text-2xl font-bold text-green-900">32 km/h</div>
            </Card>
          </div>

          <div className="mb-8">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Simulation Controls</h3>
            <div className="flex gap-2">
              <button 
                onClick={() => setSimulationActive(!simulationActive)}
                className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg font-medium transition-colors ${
                  simulationActive ? 'bg-red-100 text-red-700 hover:bg-red-200' : 'bg-green-100 text-green-700 hover:bg-green-200'
                }`}
              >
                {simulationActive ? <Square size={18} /> : <Play size={18} />}
                {simulationActive ? 'Stop' : 'Start'}
              </button>
              <button className="flex items-center justify-center px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">
                <SkipForward size={18} />
              </button>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Junctions</h3>
            <div className="flex flex-col gap-3">
              {mockJunctions.map(j => (
                <div key={j.id} onClick={() => navigate(`/junctions/${j.id}`)} className="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors">
                  <div>
                    <p className="font-medium text-gray-800">{j.name}</p>
                    <p className="text-xs text-gray-500">{j.pcu} PCU</p>
                  </div>
                  <StatusBadge 
                    status={j.status} 
                    variant={j.status.includes('A') || j.status.includes('B') ? 'success' : j.status.includes('C') || j.status.includes('D') ? 'warning' : 'error'} 
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TrafficMapPage;
