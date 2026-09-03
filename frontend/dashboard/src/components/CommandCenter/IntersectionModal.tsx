import React from 'react';
import { IntersectionData } from './CityTrafficCanvas';
import { X, Cpu, Sliders, CheckCircle2 } from 'lucide-react';

interface Props {
  intersection: IntersectionData | null;
  onClose: () => void;
  onQuickOptimize?: (id: string) => void;
  isOptimized?: boolean;
}

export const IntersectionModal: React.FC<Props> = ({
  intersection,
  onClose,
  onQuickOptimize,
  isOptimized = false,
}) => {
  if (!intersection) return null;

  const isCurrentOptimized = intersection.id === 'A-102' && isOptimized;
  const currentSpeed = isCurrentOptimized ? 42 : intersection.speed;
  const currentVehicles = isCurrentOptimized ? 480 : intersection.vehicles;
  const currentLevel = isCurrentOptimized ? 'SMOOTH' : intersection.level;

  return (
    <div className="absolute top-4 right-4 z-40 w-96 bg-white/95 rounded-3xl p-6 border border-studio-pink shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-right duration-300 font-syne">
      {/* Header */}
      <div className="flex items-start justify-between pb-4 border-b border-studio-pink/30">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-studio-coral tracking-wider font-bold">
              NODE ID: {intersection.id}
            </span>
            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider ${
              currentLevel === 'CRITICAL'
                ? 'bg-red-100 text-red-700 border border-red-300'
                : currentLevel === 'MODERATE'
                ? 'bg-amber-100 text-amber-800 border border-amber-300'
                : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
            }`}>
              {currentLevel}
            </span>
          </div>
          <h3 className="text-lg font-bold text-studio-text mt-1 leading-snug">
            {intersection.name}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-full text-studio-muted hover:text-studio-text hover:bg-studio-bgLight transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-2 gap-3 my-5 font-grotesk">
        <div className="bg-studio-bgLight/80 p-3.5 rounded-2xl border border-studio-pink/40">
          <div className="text-[11px] font-mono text-studio-muted uppercase">Vehicles Detected</div>
          <div className="text-2xl font-black text-studio-text mt-1 font-syne">
            {currentVehicles.toLocaleString()}
          </div>
          <div className="text-[10px] text-studio-muted mt-0.5">YOLOv8 Edge Tracking</div>
        </div>

        <div className="bg-studio-bgLight/80 p-3.5 rounded-2xl border border-studio-pink/40">
          <div className="text-[11px] font-mono text-studio-muted uppercase">Avg Approach Speed</div>
          <div className="text-2xl font-black text-studio-coralDark mt-1 font-syne">
            {currentSpeed} <span className="text-xs font-normal text-studio-muted">km/h</span>
          </div>
          <div className="text-[10px] text-studio-muted mt-0.5">Radar Telemetry</div>
        </div>

        <div className="bg-studio-bgLight/80 p-3.5 rounded-2xl border border-studio-pink/40">
          <div className="text-[11px] font-mono text-studio-muted uppercase">Signal Cycle</div>
          <div className="text-xl font-black text-studio-text mt-1 font-syne">
            {intersection.cycle} <span className="text-xs font-normal text-studio-muted">sec</span>
          </div>
          <div className="text-[10px] text-studio-muted mt-0.5">Dynamic Web-Time</div>
        </div>

        <div className="bg-studio-bgLight/80 p-3.5 rounded-2xl border border-studio-pink/40">
          <div className="text-[11px] font-mono text-studio-muted uppercase">AI Controller</div>
          <div className="flex items-center gap-1.5 text-emerald-700 font-bold text-sm mt-1">
            <Cpu className="w-4 h-4 text-studio-coral animate-pulse" />
            <span>{isCurrentOptimized ? 'STABILIZED' : intersection.aiStatus}</span>
          </div>
          <div className="text-[10px] text-studio-muted mt-0.5">MARL Agent Active</div>
        </div>
      </div>

      {/* Lanes Telemetry */}
      <div className="space-y-2 mb-5 font-grotesk">
        <div className="flex items-center justify-between text-xs font-mono text-studio-muted font-semibold">
          <span>LANE TELEMETRY</span>
          <span>DENSITY / STATUS</span>
        </div>
        {intersection.lanes.map((lane, idx) => {
          const laneTraffic = isCurrentOptimized && idx === 0 ? 24 : lane.traffic;
          const laneSignal = isCurrentOptimized && idx === 0 ? 'GREEN' : lane.signal;

          return (
            <div key={lane.id} className="bg-white p-2.5 rounded-xl border border-studio-pink/40 flex items-center justify-between text-xs shadow-sm">
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${
                  laneSignal === 'RED' ? 'bg-studio-coral' :
                  laneSignal === 'YELLOW' ? 'bg-amber-400' : 'bg-emerald-500'
                }`} />
                <span className="font-semibold text-studio-text">{lane.id}</span>
              </div>
              <div className="flex items-center gap-3 font-mono">
                <span className={laneTraffic > 70 ? 'text-studio-coral font-black' : 'text-studio-text font-bold'}>
                  {laneTraffic}%
                </span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                  laneSignal === 'RED' ? 'bg-red-100 text-red-700' :
                  laneSignal === 'YELLOW' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
                }`}>
                  {laneSignal}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Action CTA */}
      <div className="pt-2 font-grotesk">
        {isCurrentOptimized ? (
          <div className="w-full py-3 px-4 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-800 text-xs font-bold flex items-center justify-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            AI Optimized - Traffic Flow Balanced
          </div>
        ) : (
          <button
            onClick={() => onQuickOptimize && onQuickOptimize(intersection.id)}
            className="w-full bg-studio-black hover:bg-slate-900 text-white py-3 rounded-full text-xs font-bold flex items-center justify-center gap-2 tracking-wider uppercase shadow-orb transition-all"
          >
            <Sliders className="w-4 h-4 text-studio-coral" />
            Optimize Intersection Signals
          </button>
        )}
      </div>
    </div>
  );
};
