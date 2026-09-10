import React from 'react';
import { IntersectionData } from './CityTrafficCanvas';
import { X } from 'lucide-react';
import { TelemetrySourceBadge } from '../TelemetrySourceBadge';

interface Props {
  intersection: IntersectionData | null;
  onClose: () => void;
  onQuickOptimize?: (id: string) => void;
  isOptimized?: boolean;
}

// SN-012g/§13.10: this modal previously showed "Vehicles Detected"/"Avg
// Approach Speed"/"Signal Cycle"/per-lane density numbers captioned "YOLOv8
// Edge Tracking" and "Radar Telemetry" — all hardcoded on the node, with a
// "Optimize Intersection Signals" button that snapped them to a second set
// of hardcoded values. Neither a vision pipeline nor the control service
// feeds this component, so it now says that plainly instead of inventing
// numbers for either state.
export const IntersectionModal: React.FC<Props> = ({ intersection, onClose }) => {
  if (!intersection) return null;

  return (
    <div className="absolute top-4 right-4 z-40 w-96 bg-white/95 rounded-3xl p-6 border border-studio-pink shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-right duration-300 font-syne">
      {/* Header */}
      <div className="flex items-start justify-between pb-4 border-b border-studio-pink/30">
        <div>
          <span className="font-mono text-xs text-studio-coral tracking-wider font-bold">
            NODE ID: {intersection.id}
          </span>
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

      <div className="my-5 py-6 flex flex-col items-center justify-center gap-2 text-center">
        <TelemetrySourceBadge source={null} />
        <p className="text-xs text-studio-muted max-w-xs">
          No vision or control-service telemetry is wired to this illustrative
          node yet — vehicle count, speed, cycle, and lane density aren't real.
        </p>
      </div>

      {/* Lanes — ids only, no fabricated density/signal state */}
      <div className="space-y-2 font-grotesk">
        <div className="text-xs font-mono text-studio-muted font-semibold">LANES</div>
        {intersection.lanes.map((lane) => (
          <div key={lane.id} className="bg-white p-2.5 rounded-xl border border-studio-pink/40 flex items-center justify-between text-xs shadow-sm">
            <span className="font-semibold text-studio-text">{lane.id}</span>
            <TelemetrySourceBadge source={null} showIcon={false} />
          </div>
        ))}
      </div>
    </div>
  );
};
