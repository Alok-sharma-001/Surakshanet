import React from 'react';
import {
  SlidersHorizontal,
  Layers,
} from 'lucide-react';
import { TelemetrySourceBadge } from '../TelemetrySourceBadge';

// SN-012g/§13.10: this whole panel used to be a scripted demo — an "Apply AI
// Recommendation" button that ran a 3s fake countdown ("DISPATCHING MARL
// ACTUATOR") and then snapped three lane density numbers, a speed, and a
// throughput/wait improvement to hardcoded values (24%, 44 km/h, +42%,
// -68%), none of it backed by a camera feed, a density model, or the
// control service. There's no per-lane camera/density telemetry wired to
// this page yet, so it shows that honestly instead of a canned before/after.
interface Props {
  onOptimizedStateChange?: (isOptimized: boolean) => void;
}

export const SignalControlInteractive: React.FC<Props> = () => {
  return (
    <div className="w-full bg-white rounded-3xl p-6 md:p-8 border border-studio-pink/40 shadow-studio-card relative overflow-hidden font-syne">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-studio-pink/30 relative z-10">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-studio-coral tracking-wider uppercase">
              NODE ID: A-102
            </span>
            <span className="text-studio-muted">•</span>
            <span className="font-grotesk text-xs text-studio-muted font-medium">DOWNTOWN ARTERIAL CORRIDOR</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-black text-studio-text tracking-tight mt-1">
            Intelligent Signal Control
          </h2>
        </div>

        <div className="flex items-center gap-3 font-grotesk">
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-studio-bgLight border border-studio-pink/40 text-xs font-mono font-bold text-studio-text">
            <SlidersHorizontal className="w-3.5 h-3.5 text-studio-coral" />
            <span>MODE: <strong className="text-studio-coralDark">AUTONOMOUS MARL</strong></span>
          </div>
        </div>
      </div>

      {/* Honest state: no per-lane camera/density telemetry is wired to this
          page. The real control loop (services/control_service/) drives J0-J3
          directly against SUMO — see the Signal Control page for its live
          decisions — but nothing here reads from it yet. */}
      <div className="my-8 py-10 flex flex-col items-center justify-center gap-3 text-center relative z-10">
        <TelemetrySourceBadge source={null} />
        <p className="text-sm text-studio-muted max-w-md">
          This panel is not yet wired to live per-lane camera/density telemetry
          or the control service. No lane data, recommendation, or "optimize"
          action shown here would be real.
        </p>
      </div>

      {/* Closed-loop Pipeline Flow — illustrative only */}
      <div className="pt-4 border-t border-studio-pink/30 flex flex-wrap items-center justify-between text-xs font-mono text-studio-muted gap-2">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-studio-coral" />
          <span className="text-studio-text font-bold">Intended Closed-Loop Pipeline:</span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-grotesk font-semibold">
          <span className="px-2.5 py-1 bg-studio-bgLight rounded-full border border-studio-pink/40 text-studio-text">1. Camera Feed</span>
          <span className="text-studio-coral">→</span>
          <span className="px-2.5 py-1 bg-studio-bgLight rounded-full border border-studio-pink/40 text-studio-text">2. YOLOv8s Model</span>
          <span className="text-studio-coral">→</span>
          <span className="px-2.5 py-1 bg-studio-bgLight rounded-full border border-studio-pink/40 text-studio-text">3. Density Analysis</span>
          <span className="text-studio-coral">→</span>
          <span className="px-2.5 py-1 bg-studio-bgLight rounded-full border border-studio-pink/40 text-studio-text">4. MARL Decision</span>
          <span className="text-studio-coral">→</span>
          <span className="px-2.5 py-1 bg-studio-bgLight rounded-full border border-studio-pink/40 text-studio-text">5. Actuator Signal</span>
        </div>
      </div>
    </div>
  );
};
