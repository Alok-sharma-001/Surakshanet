import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, MapPin, Activity, Clock, ArrowRight } from 'lucide-react';
import clsx from 'clsx';

type Status = 'Normal' | 'Congested' | 'MARL Active' | 'Offline';

interface Junction {
  id: string;
  name: string;
  status: Status;
  pcu: number;
  speed: number;
  queue: number;
}

const MOCK_JUNCTIONS: Junction[] = [
  { id: 'BLR-CEN-042', name: 'MG Road - Brigade Junction', status: 'Normal', pcu: 342, speed: 28, queue: 12 },
  { id: 'BLR-SE-018', name: 'Koramangala Signal', status: 'Congested', pcu: 512, speed: 14, queue: 85 },
  { id: 'BLR-E-091', name: 'Whitefield Bypass', status: 'MARL Active', pcu: 289, speed: 32, queue: 8 },
  { id: 'BLR-N-005', name: 'Hebbal Flyover', status: 'Normal', pcu: 198, speed: 42, queue: 5 },
  { id: 'BLR-SE-001', name: 'Silk Board Junction', status: 'Congested', pcu: 645, speed: 8, queue: 120 },
  { id: 'BLR-E-044', name: 'Marathahalli Bridge', status: 'Normal', pcu: 267, speed: 35, queue: 15 },
];

const JunctionsPage: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<Status | 'All'>('All');

  const filteredJunctions = MOCK_JUNCTIONS.filter(j => {
    const matchesSearch = j.name.toLowerCase().includes(search.toLowerCase()) || j.id.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = filter === 'All' || j.status === filter;
    return matchesSearch && matchesFilter;
  });

  const getStatusColor = (status: Status) => {
    switch(status) {
      case 'Normal': return 'bg-emerald-100 text-emerald-700 border-emerald-200';
      case 'Congested': return 'bg-red-100 text-red-700 border-red-200';
      case 'MARL Active': return 'bg-teal-100 text-teal-700 border-teal-200';
      case 'Offline': return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Junction Network</h1>
        <p className="text-sm text-slate-500 mt-1">Monitoring 150 active intersections</p>
      </div>

      {/* Summary Mini Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Junctions', value: '150' },
          { label: 'MARL Controlled', value: '42' },
          { label: 'Manual Mode', value: '8' },
          { label: 'Offline', value: '2' }
        ].map((stat, i) => (
          <div key={i} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5 flex flex-col justify-center">
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">{stat.label}</div>
            <div className="text-3xl font-bold text-slate-900">{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-slate-400" />
          </div>
          <input
            type="text"
            className="w-full border border-slate-200 rounded-lg pl-10 pr-4 py-3 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none transition-all shadow-sm"
            placeholder="Search junctions by name or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as Status | 'All')}
          className="border border-slate-200 rounded-lg px-4 py-3 bg-white text-sm focus:ring-2 focus:ring-sky-500 outline-none shadow-sm min-w-[160px] text-slate-700"
        >
          <option value="All">All Status</option>
          <option value="Normal">Normal</option>
          <option value="Congested">Congested</option>
          <option value="MARL Active">MARL Active</option>
          <option value="Offline">Offline</option>
        </select>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredJunctions.map((junction) => (
          <div
            key={junction.id}
            onClick={() => navigate(`/junctions/${junction.id}`)}
            className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 hover:shadow-md hover:border-sky-300 transition-all cursor-pointer flex flex-col h-full group"
          >
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="font-semibold text-slate-900 line-clamp-1" title={junction.name}>{junction.name}</h3>
                <div className="font-mono text-xs text-slate-500 mt-1">{junction.id}</div>
              </div>
              <span className={clsx("px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full border", getStatusColor(junction.status))}>
                {junction.status}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-4 my-4 py-4 border-y border-slate-100 flex-1">
              <div className="flex flex-col items-center justify-center text-center">
                <Activity className="w-4 h-4 text-slate-400 mb-1" />
                <span className="text-lg font-bold text-slate-700">{junction.pcu}</span>
                <span className="text-[10px] text-slate-500 uppercase">PCU</span>
              </div>
              <div className="flex flex-col items-center justify-center text-center border-x border-slate-100">
                <Clock className="w-4 h-4 text-slate-400 mb-1" />
                <span className="text-lg font-bold text-slate-700">{junction.speed}</span>
                <span className="text-[10px] text-slate-500 uppercase">km/h</span>
              </div>
              <div className="flex flex-col items-center justify-center text-center">
                <MapPin className="w-4 h-4 text-slate-400 mb-1" />
                <span className="text-lg font-bold text-slate-700">{junction.queue}</span>
                <span className="text-[10px] text-slate-500 uppercase">m Queue</span>
              </div>
            </div>

            <div className="mt-auto flex items-center text-sm font-medium text-teal-600 group-hover:text-teal-700 transition-colors">
              <span>View Details</span>
              <ArrowRight className="w-4 h-4 ml-1 transform group-hover:translate-x-1 transition-transform" />
            </div>
          </div>
        ))}
      </div>
      
      {filteredJunctions.length === 0 && (
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-12 text-center text-slate-500">
          No junctions found matching your criteria.
        </div>
      )}
    </div>
  );
};

export default JunctionsPage;
