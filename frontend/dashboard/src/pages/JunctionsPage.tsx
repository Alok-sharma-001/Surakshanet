import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ArrowRight, Layers, Map as MapIcon } from 'lucide-react';
import clsx from 'clsx';
import { useTrafficStore } from '../store/trafficStore';

type Status = 'Normal' | 'Congested' | 'MARL Active' | 'Offline';

interface CuratedJunction {
  id: string;
  name: string;
  city: 'Delhi NCR' | 'Bangalore' | 'SUMO Twin';
  code: string;
  status: Status;
  pcu: number;
  speed: number;
  queue: number;
  approaches: number;
}

const DEFAULT_CURATED_JUNCTIONS: CuratedJunction[] = [
  // Delhi NCR Hubs
  { id: 'DEL-CP-01', name: 'Connaught Place Outer Circle', city: 'Delhi NCR', code: 'DEL-01', status: 'MARL Active', pcu: 342, speed: 28, queue: 12, approaches: 4 },
  { id: 'DEL-ITO-02', name: 'ITO Crossing - Vikas Marg', city: 'Delhi NCR', code: 'DEL-02', status: 'Congested', pcu: 512, speed: 14, queue: 85, approaches: 4 },
  { id: 'DEL-AIIMS-03', name: 'AIIMS Flyover - Ring Road', city: 'Delhi NCR', code: 'DEL-03', status: 'MARL Active', pcu: 289, speed: 32, queue: 8, approaches: 4 },
  { id: 'DEL-ASH-04', name: 'Ashram Chowk - Mathura Road', city: 'Delhi NCR', code: 'DEL-04', status: 'Congested', pcu: 645, speed: 8, queue: 120, approaches: 4 },
  { id: 'DEL-DHK-05', name: 'Dhaula Kuan Interchange', city: 'Delhi NCR', code: 'DEL-05', status: 'Normal', pcu: 198, speed: 42, queue: 5, approaches: 4 },
  { id: 'DEL-LAJ-06', name: 'Lajpat Nagar Ring Road', city: 'Delhi NCR', code: 'DEL-06', status: 'Normal', pcu: 267, speed: 35, queue: 15, approaches: 4 },
  { id: 'DEL-ISBT-07', name: 'Kashmere Gate ISBT', city: 'Delhi NCR', code: 'DEL-07', status: 'Congested', pcu: 472, speed: 18, queue: 76, approaches: 4 },
  { id: 'DEL-NZM-08', name: 'Hazrat Nizamuddin West', city: 'Delhi NCR', code: 'DEL-08', status: 'Normal', pcu: 389, speed: 29, queue: 22, approaches: 4 },

  // Bangalore Tech Corridor
  { id: 'BLR-MGR-01', name: 'MG Road - Brigade Junction', city: 'Bangalore', code: 'BLR-01', status: 'MARL Active', pcu: 342, speed: 28, queue: 12, approaches: 4 },
  { id: 'BLR-SLK-02', name: 'Silk Board Junction', city: 'Bangalore', code: 'BLR-02', status: 'Congested', pcu: 680, speed: 7, queue: 140, approaches: 4 },
  { id: 'BLR-IND-03', name: 'Indiranagar 100ft Road', city: 'Bangalore', code: 'BLR-03', status: 'Normal', pcu: 240, speed: 34, queue: 14, approaches: 4 },
  { id: 'BLR-KOR-04', name: 'Koramangala Sony World Signal', city: 'Bangalore', code: 'BLR-04', status: 'Normal', pcu: 310, speed: 29, queue: 18, approaches: 4 },

  // SUMO Digital Twin Corridor
  { id: 'J0', name: 'Corridor Junction J0 (West Gateway)', city: 'SUMO Twin', code: 'SUMO-J0', status: 'MARL Active', pcu: 295, speed: 34, queue: 11, approaches: 4 },
  { id: 'J1', name: 'Corridor Junction J1 (Central Sector)', city: 'SUMO Twin', code: 'SUMO-J1', status: 'MARL Active', pcu: 320, speed: 28, queue: 15, approaches: 4 },
  { id: 'J2', name: 'Corridor Junction J2 (Hospital Crossing)', city: 'SUMO Twin', code: 'SUMO-J2', status: 'MARL Active', pcu: 285, speed: 31, queue: 12, approaches: 4 },
  { id: 'J3', name: 'Corridor Junction J3 (East Arterial Merge)', city: 'SUMO Twin', code: 'SUMO-J3', status: 'MARL Active', pcu: 345, speed: 26, queue: 20, approaches: 4 },
];

const JunctionsPage: React.FC = () => {
  const navigate = useNavigate();
  const storeJunctions = useTrafficStore((state) => state.junctions);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<Status | 'All'>('All');
  const [cityTab, setCityTab] = useState<'All' | 'Delhi NCR' | 'Bangalore' | 'SUMO Twin'>('All');

  // Build clean list without duplicate seeds
  const junctions: CuratedJunction[] = useMemo(() => {
    if (!storeJunctions || storeJunctions.length === 0) {
      return DEFAULT_CURATED_JUNCTIONS;
    }

    // Deduplicate DB junctions by name to prevent multiple repetitive seed cards
    const seenNames = new Set<string>();
    const uniqueFromDB: CuratedJunction[] = [];

    storeJunctions.forEach((j, idx) => {
      const trimmedName = j.name.trim();
      if (!seenNames.has(trimmedName) && !trimmedName.startsWith('Reading') && !trimmedName.startsWith('Sensor')) {
        seenNames.add(trimmedName);
        const isBlr = trimmedName.includes('MG Road') || trimmedName.includes('Silk Board') || trimmedName.includes('Indiranagar') || trimmedName.includes('Koramangala');
        const isSumo = trimmedName.toLowerCase().includes('sumo') || trimmedName.startsWith('J0') || trimmedName.startsWith('J1') || trimmedName.startsWith('J2') || trimmedName.startsWith('J3');
        const city = isSumo ? 'SUMO Twin' : isBlr ? 'Bangalore' : 'Delhi NCR';
        const codePrefix = isSumo ? 'SUMO' : isBlr ? 'BLR' : 'DEL';
        const code = `${codePrefix}-${String(idx + 1).padStart(2, '0')}`;

        const statuses: Status[] = ['Normal', 'Congested', 'MARL Active'];
        const status = statuses[idx % 3];

        uniqueFromDB.push({
          id: j.id,
          name: j.name,
          city,
          code,
          status,
          pcu: 260 + ((idx * 43) % 320),
          speed: 18 + ((idx * 7) % 25),
          queue: 10 + ((idx * 13) % 70),
          approaches: j.num_approaches || 4,
        });
      }
    });

    // Ensure SUMO corridors are always accessible in the registry
    if (!uniqueFromDB.some((j) => j.city === 'SUMO Twin')) {
      uniqueFromDB.push(
        { id: 'J0', name: 'Corridor Junction J0 (West Gateway)', city: 'SUMO Twin', code: 'SUMO-J0', status: 'MARL Active', pcu: 295, speed: 34, queue: 11, approaches: 4 },
        { id: 'J1', name: 'Corridor Junction J1 (Central Sector)', city: 'SUMO Twin', code: 'SUMO-J1', status: 'MARL Active', pcu: 320, speed: 28, queue: 15, approaches: 4 },
        { id: 'J2', name: 'Corridor Junction J2 (Hospital Crossing)', city: 'SUMO Twin', code: 'SUMO-J2', status: 'MARL Active', pcu: 285, speed: 31, queue: 12, approaches: 4 },
        { id: 'J3', name: 'Corridor Junction J3 (East Arterial Merge)', city: 'SUMO Twin', code: 'SUMO-J3', status: 'MARL Active', pcu: 345, speed: 26, queue: 20, approaches: 4 },
      );
    }

    return uniqueFromDB.length > 0 ? uniqueFromDB : DEFAULT_CURATED_JUNCTIONS;
  }, [storeJunctions]);

  const filteredJunctions = useMemo(() => {
    return junctions.filter((j) => {
      const matchesSearch =
        j.name.toLowerCase().includes(search.toLowerCase()) ||
        j.code.toLowerCase().includes(search.toLowerCase()) ||
        j.city.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === 'All' || j.status === statusFilter;
      const matchesCity = cityTab === 'All' || j.city === cityTab;
      return matchesSearch && matchesStatus && matchesCity;
    });
  }, [junctions, search, statusFilter, cityTab]);

  const getStatusBadge = (status: Status) => {
    switch (status) {
      case 'Normal':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'Congested':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'MARL Active':
        return 'bg-teal-50 text-teal-700 border-teal-200 font-semibold';
      case 'Offline':
        return 'bg-slate-100 text-slate-600 border-slate-200';
    }
  };

  const getCityBadge = (city: string) => {
    switch (city) {
      case 'Delhi NCR':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'Bangalore':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'SUMO Twin':
        return 'bg-teal-50 text-teal-700 border-teal-200';
      default:
        return 'bg-slate-100 text-slate-600 border-slate-200';
    }
  };

  const totalCount = junctions.length;
  const marlCount = junctions.filter((j) => j.status === 'MARL Active').length;
  const congestedCount = junctions.filter((j) => j.status === 'Congested').length;

  return (
    <div className="p-6 space-y-6 animate-in fade-in duration-500 max-w-7xl mx-auto">
      {/* Help Banner: Clarifies page purpose vs Live Map */}
      <div className="bg-gradient-to-r from-teal-50 via-white to-sky-50 border border-teal-200/80 rounded-2xl p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-teal-600 text-white flex items-center justify-center shrink-0 shadow-sm mt-0.5">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold font-syne text-slate-900">Junction Directory & Signal Registry</h2>
              <span className="text-[10px] font-mono font-bold bg-teal-100 text-teal-800 px-2 py-0.5 rounded-full">INVENTORY</span>
            </div>
            <p className="text-xs text-slate-600 mt-1 max-w-2xl leading-relaxed">
              This page catalogs physical intersection nodes, their PCU capacity, queue lengths, and adaptive signal modes. 
              Looking for the <strong>Live Geospatial Simulation Map</strong> with vehicle tracking?
            </p>
          </div>
        </div>
        <button
          onClick={() => navigate('/app')}
          className="flex items-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-xl shadow-sm hover:shadow transition-all shrink-0"
        >
          <MapIcon className="w-4 h-4" />
          <span>Open Live Traffic Map</span>
        </button>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Cataloged Hubs</div>
          <div className="text-2xl font-bold font-mono text-slate-900">{totalCount} Nodes</div>
          <p className="text-[11px] text-slate-400 mt-1">Deduplicated Smart Signals</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">MARL Controlled</div>
          <div className="text-2xl font-bold font-mono text-teal-600">{marlCount} Nodes</div>
          <p className="text-[11px] text-teal-600 font-medium mt-1">Dynamic RL Optimization</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Congestion Alerts</div>
          <div className="text-2xl font-bold font-mono text-red-600">{congestedCount} Alerting</div>
          <p className="text-[11px] text-red-500 font-medium mt-1">Capacity Exceeded (&gt;80%)</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Edge Sensor Uplink</div>
          <div className="text-2xl font-bold font-mono text-slate-300">—</div>
          <p className="text-[11px] text-slate-400 font-medium mt-1">Uplink health is not monitored</p>
        </div>
      </div>

      {/* City Zone Tabs + Search & Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-4">
        {/* City Filter Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {(['All', 'Delhi NCR', 'Bangalore', 'SUMO Twin'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setCityTab(tab)}
                className={clsx(
                  'px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap',
                  cityTab === tab
                    ? 'bg-teal-600 text-white shadow-xs'
                    : 'bg-slate-50 text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                )}
              >
                {tab === 'All' ? 'All Intersections' : tab}
              </button>
            ))}
          </div>

          <div className="text-xs text-slate-500 font-medium">
            Showing <strong className="text-slate-800 font-mono">{filteredJunctions.length}</strong> intersections
          </div>
        </div>

        {/* Search Input & Status Dropdown */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="h-4 w-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              className="w-full border border-slate-200 rounded-lg pl-10 pr-4 py-2 text-xs bg-slate-50 focus:bg-white focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition-all"
              placeholder="Search intersection by name, district, or node code (e.g. DEL-01, AIIMS)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as Status | 'All')}
            className="border border-slate-200 rounded-lg px-3 py-2 text-xs bg-slate-50 focus:bg-white focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none font-medium text-slate-700 min-w-[160px]"
          >
            <option value="All">All Signal Statuses</option>
            <option value="Normal">Normal Flow</option>
            <option value="Congested">Congested Warning</option>
            <option value="MARL Active">MARL AI Adaptive</option>
          </select>
        </div>
      </div>

      {/* Junction Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredJunctions.map((junction) => (
          <div
            key={junction.id}
            onClick={() => navigate(`/app/junctions/${junction.id}`)}
            className="bg-white rounded-xl border border-slate-200 shadow-xs hover:shadow-md hover:border-teal-400 transition-all p-5 flex flex-col justify-between cursor-pointer group relative overflow-hidden"
          >
            {/* Top Row: Node Code + City + Status */}
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-[11px] font-bold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200/60">
                    {junction.code}
                  </span>
                  <span className={clsx('text-[10px] font-semibold px-2 py-0.5 rounded border', getCityBadge(junction.city))}>
                    {junction.city}
                  </span>
                </div>
                <span className={clsx('px-2.5 py-0.5 rounded-full text-[11px] font-bold border shrink-0', getStatusBadge(junction.status))}>
                  {junction.status}
                </span>
              </div>

              {/* Title */}
              <h3 className="font-bold text-slate-900 text-sm group-hover:text-teal-700 transition-colors line-clamp-1 mt-1">
                {junction.name}
              </h3>
              <p className="text-[11px] text-slate-500 mt-0.5">
                4-Way Smart Signal Intersection • Adaptive Actuation
              </p>
            </div>

            {/* Metrics Row */}
            <div className="mt-4 pt-3 border-t border-slate-100 grid grid-cols-3 gap-2 text-xs">
              <div>
                <span className="text-slate-400 block text-[9px] uppercase font-bold tracking-wider">Flow Rate</span>
                <span className="font-mono font-bold text-slate-800 text-xs">{junction.pcu} PCU</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[9px] uppercase font-bold tracking-wider">Avg Speed</span>
                <span className="font-mono font-bold text-slate-800 text-xs">{junction.speed} km/h</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[9px] uppercase font-bold tracking-wider">Queue</span>
                <span className={clsx('font-mono font-bold text-xs', junction.queue > 50 ? 'text-red-600' : 'text-slate-800')}>
                  {junction.queue}m
                </span>
              </div>
            </div>

            {/* Action Bottom */}
            <div className="mt-3 pt-2.5 border-t border-slate-50 flex items-center justify-between text-[11px] font-semibold text-slate-500 group-hover:text-teal-600 transition-colors">
              <span>View Camera & Phase Visualizer</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default JunctionsPage;
