import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ArrowRight } from 'lucide-react';
import clsx from 'clsx';
import { useTrafficStore } from '../store/trafficStore';

type Status = 'Normal' | 'Congested' | 'MARL Active' | 'Offline';

const DEFAULT_FALLBACKS = [
  { id: 'DEL-CP-01', name: 'Connaught Place Outer Circle', status: 'MARL Active' as Status, pcu: 342, speed: 28, queue: 12 },
  { id: 'DEL-ITO-02', name: 'ITO Crossing - Vikas Marg', status: 'Congested' as Status, pcu: 512, speed: 14, queue: 85 },
  { id: 'DEL-AIIMS-03', name: 'AIIMS Flyover - Ring Road', status: 'MARL Active' as Status, pcu: 289, speed: 32, queue: 8 },
  { id: 'DEL-ASH-04', name: 'Ashram Chowk - Mathura Road', status: 'Congested' as Status, pcu: 645, speed: 8, queue: 120 },
  { id: 'DEL-DHK-05', name: 'Dhaula Kuan Interchange', status: 'Normal' as Status, pcu: 198, speed: 42, queue: 5 },
  { id: 'DEL-LAJ-06', name: 'Lajpat Nagar Ring Road', status: 'Normal' as Status, pcu: 267, speed: 35, queue: 15 },
  { id: 'BLR-MGR-01', name: 'MG Road - Brigade Junction', status: 'MARL Active' as Status, pcu: 342, speed: 28, queue: 12 },
  { id: 'BLR-SLK-02', name: 'Silk Board Junction', status: 'Congested' as Status, pcu: 680, speed: 7, queue: 140 },
  { id: 'BLR-IND-03', name: 'Indiranagar 100ft Road', status: 'Normal' as Status, pcu: 240, speed: 34, queue: 14 },
  { id: 'BLR-KOR-04', name: 'Koramangala Sony World Signal', status: 'Normal' as Status, pcu: 310, speed: 29, queue: 18 },
];

const JunctionsPage: React.FC = () => {
  const navigate = useNavigate();
  const storeJunctions = useTrafficStore((state) => state.junctions);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<Status | 'All'>('All');

  const junctions = storeJunctions.length > 0
    ? storeJunctions.map((j, idx) => {
        const statuses: Status[] = ['Normal', 'Congested', 'MARL Active'];
        const st = statuses[idx % 3];
        return {
          id: j.id,
          name: j.name,
          status: st,
          pcu: 250 + (idx * 37) % 350,
          speed: 18 + (idx * 5) % 30,
          queue: 10 + (idx * 11) % 75,
        };
      })
    : DEFAULT_FALLBACKS;

  const filteredJunctions = junctions.filter(j => {
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

  const totalCount = junctions.length;
  const marlCount = junctions.filter(j => j.status === 'MARL Active').length;
  const congestedCount = junctions.filter(j => j.status === 'Congested').length;

  return (
    <div className="p-6 space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold font-syne text-slate-900">Junction Network</h1>
        <p className="text-sm text-slate-500 mt-1">
          Real-time topology monitoring across {totalCount} active smart intersections
        </p>
      </div>

      {/* Summary Mini Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Junctions', value: totalCount.toString() },
          { label: 'MARL Controlled', value: marlCount.toString() },
          { label: 'Congestion Alerts', value: congestedCount.toString() },
          { label: 'Sensor Uplink Status', value: '100%' }
        ].map((stat, i) => (
          <div key={i} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5 flex flex-col justify-center">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">{stat.label}</div>
            <div className="text-3xl font-bold font-mono text-slate-900">{stat.value}</div>
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
            className="w-full border border-slate-200 rounded-lg pl-10 pr-4 py-3 bg-white text-sm focus:ring-2 focus:ring-teal-500 outline-none transition-all shadow-sm"
            placeholder="Search junctions by name or UUID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as Status | 'All')}
          className="border border-slate-200 rounded-lg px-4 py-3 bg-white text-sm focus:ring-2 focus:ring-teal-500 outline-none shadow-sm min-w-[160px] text-slate-700 font-medium"
        >
          <option value="All">All Statuses</option>
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
            onClick={() => navigate(`/app/junctions/${junction.id}`)}
            className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm hover:shadow-md hover:border-teal-300 transition-all p-5 flex flex-col justify-between cursor-pointer group"
          >
            <div>
              <div className="flex justify-between items-start gap-2 mb-2">
                <h3 className="font-bold text-slate-800 text-base group-hover:text-teal-700 transition-colors">
                  {junction.name}
                </h3>
                <span className={clsx("px-2.5 py-0.5 rounded-full text-xs font-bold border shrink-0", getStatusColor(junction.status))}>
                  {junction.status}
                </span>
              </div>
              <div className="text-xs font-mono text-slate-400 mb-4">{junction.id}</div>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
              <div>
                <span className="text-slate-400 block text-[10px] uppercase">Throughput</span>
                <span className="font-mono font-bold text-slate-800">{junction.pcu} PCU</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase">Velocity</span>
                <span className="font-mono font-bold text-slate-800">{junction.speed} km/h</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px] uppercase">Queue</span>
                <span className="font-mono font-bold text-slate-800">{junction.queue}m</span>
              </div>
              <div className="p-2 rounded-lg bg-slate-50 group-hover:bg-teal-50 group-hover:text-teal-600 transition-colors">
                <ArrowRight className="w-4 h-4" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default JunctionsPage;
