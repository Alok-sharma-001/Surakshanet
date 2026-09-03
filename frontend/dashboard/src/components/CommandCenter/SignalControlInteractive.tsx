import React, { useState } from 'react';
import { 
  Sparkles, 
  ArrowRight, 
  CheckCircle2, 
  RotateCcw, 
  AlertTriangle, 
  SlidersHorizontal,
  Layers,
  Zap
} from 'lucide-react';

interface Props {
  onOptimizedStateChange?: (isOptimized: boolean) => void;
}

export const SignalControlInteractive: React.FC<Props> = ({ onOptimizedStateChange }) => {
  const [isApplying, setIsApplying] = useState(false);
  const [isOptimized, setIsOptimized] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);

  // Lanes dynamic state
  const lane1Density = isOptimized ? 24 : 87;
  const lane1Signal = isOptimized ? 'GREEN' : 'RED';
  const lane1Speed = isOptimized ? 44 : 12;

  const lane2Density = 32;
  const lane3Density = 61;

  const handleApplyRecommendation = () => {
    setIsApplying(true);
    setCountdown(3);

    // Simulate transition
    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev !== null && prev <= 1) {
          clearInterval(interval);
          setIsApplying(false);
          setIsOptimized(true);
          setCountdown(null);
          if (onOptimizedStateChange) onOptimizedStateChange(true);
          return null;
        }
        return prev ? prev - 1 : null;
      });
    }, 600);
  };

  const handleReset = () => {
    setIsOptimized(false);
    if (onOptimizedStateChange) onOptimizedStateChange(false);
  };

  return (
    <div className="w-full bg-white rounded-3xl p-6 md:p-8 border border-studio-pink/40 shadow-studio-card relative overflow-hidden font-syne">
      {/* Background ambient blush */}
      <div className={`absolute top-0 right-0 w-96 h-96 rounded-full blur-3xl pointer-events-none transition-all duration-700 ${
        isOptimized ? 'bg-emerald-100/40' : 'bg-studio-pink/30'
      }`} />

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
          <h2 className="text-2xl sm:text-3xl font-black text-studio-text tracking-tight mt-1 flex items-center gap-3">
            Intelligent Signal Control
            {isOptimized && (
              <span className="text-xs font-mono font-bold px-3 py-1 bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-full flex items-center gap-1.5 shadow-sm">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                MARL OPTIMIZED
              </span>
            )}
          </h2>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3 font-grotesk">
          {isOptimized && (
            <button
              onClick={handleReset}
              className="px-4 py-2 rounded-full bg-studio-bgLight hover:bg-studio-pink/40 text-studio-coralDark border border-studio-pink text-xs flex items-center gap-1.5 font-bold transition-all shadow-sm"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Demo
            </button>
          )}
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-studio-bgLight border border-studio-pink/40 text-xs font-mono font-bold text-studio-text">
            <SlidersHorizontal className="w-3.5 h-3.5 text-studio-coral" />
            <span>MODE: <strong className="text-studio-coralDark">AUTONOMOUS MARL</strong></span>
          </div>
        </div>
      </div>

      {/* Main Interaction Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 my-8 relative z-10 font-grotesk">
        {/* Left 7 cols: 3-Lane Status Cards */}
        <div className="lg:col-span-7 space-y-4">
          <div className="text-xs font-mono text-studio-muted flex items-center justify-between px-1 uppercase tracking-wider font-semibold">
            <span>ACTIVE APPROACH LANES</span>
            <span>REAL-TIME DENSITY TELEMETRY</span>
          </div>

          {/* Lane 01 (Congested / Targeted Lane) */}
          <div className={`p-5 rounded-2xl border transition-all duration-500 ${
            isOptimized
              ? 'bg-emerald-50/70 border-emerald-300 shadow-sm'
              : 'bg-red-50/60 border-red-200 shadow-sm'
          }`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                {/* Traffic Light Mini Widget */}
                <div className="bg-studio-black px-2.5 py-1 rounded-full border border-slate-700 flex items-center gap-1.5 shadow-orb">
                  <span className={`w-3 h-3 rounded-full transition-all duration-300 ${
                    lane1Signal === 'RED' ? 'bg-red-500 shadow-red-glow animate-pulse' : 'bg-red-950 opacity-40'
                  }`} />
                  <span className="w-3 h-3 rounded-full bg-amber-950 opacity-40" />
                  <span className={`w-3 h-3 rounded-full transition-all duration-300 ${
                    lane1Signal === 'GREEN' ? 'bg-emerald-400 shadow-green-glow animate-pulse' : 'bg-emerald-950 opacity-40'
                  }`} />
                </div>

                <div>
                  <h4 className="text-base font-bold text-studio-text flex items-center gap-2 font-syne">
                    Lane 01 (Northbound Arterial)
                    {!isOptimized && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-700 border border-red-300">
                        BOTTLENECK
                      </span>
                    )}
                  </h4>
                  <p className="text-xs text-studio-muted font-mono">Camera Feed: Cam-North-01</p>
                </div>
              </div>

              {/* Status Badge */}
              <div className="text-right">
                <div className={`text-2xl font-black font-mono tracking-tight transition-colors duration-500 ${
                  isOptimized ? 'text-emerald-600' : 'text-red-600'
                }`}>
                  {lane1Density}%
                </div>
                <div className="text-[11px] font-mono text-studio-muted uppercase">
                  Avg: {lane1Speed} km/h
                </div>
              </div>
            </div>

            {/* Density Progress Bar */}
            <div className="w-full bg-white h-3 rounded-full overflow-hidden p-0.5 border border-studio-pink/40 shadow-inner">
              <div
                className={`h-full rounded-full transition-all duration-1000 ease-out ${
                  isOptimized
                    ? 'bg-gradient-to-r from-emerald-400 to-teal-500'
                    : 'bg-gradient-to-r from-amber-400 to-studio-coral'
                }`}
                style={{ width: `${lane1Density}%` }}
              />
            </div>
          </div>

          {/* Lane 02 (Green / Free Flow) */}
          <div className="p-4 rounded-2xl border border-studio-pink/30 bg-studio-bgLight/50">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <div className="bg-studio-black px-2.5 py-1 rounded-full border border-slate-700 flex items-center gap-1.5 shadow-orb">
                  <span className="w-3 h-3 rounded-full bg-red-950 opacity-40" />
                  <span className="w-3 h-3 rounded-full bg-amber-950 opacity-40" />
                  <span className="w-3 h-3 rounded-full bg-emerald-400 shadow-green-glow" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-studio-text font-syne">Lane 02 (East Bypass)</h4>
                  <p className="text-xs text-studio-muted font-mono">Camera Feed: Cam-East-02</p>
                </div>
              </div>
              <div className="text-right">
                <span className="text-xl font-bold font-mono text-emerald-600">{lane2Density}%</span>
                <span className="text-[11px] text-studio-muted block font-mono">Avg: 48 km/h</span>
              </div>
            </div>
            <div className="w-full bg-white h-2 rounded-full overflow-hidden border border-studio-pink/30">
              <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${lane2Density}%` }} />
            </div>
          </div>

          {/* Lane 03 (Moderate / Yellow) */}
          <div className="p-4 rounded-2xl border border-studio-pink/30 bg-studio-bgLight/50">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <div className="bg-studio-black px-2.5 py-1 rounded-full border border-slate-700 flex items-center gap-1.5 shadow-orb">
                  <span className="w-3 h-3 rounded-full bg-red-950 opacity-40" />
                  <span className="w-3 h-3 rounded-full bg-amber-400 shadow-amber-glow animate-pulse" />
                  <span className="w-3 h-3 rounded-full bg-emerald-950 opacity-40" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-studio-text font-syne">Lane 03 (Southbound Connector)</h4>
                  <p className="text-xs text-studio-muted font-mono">Camera Feed: Cam-South-03</p>
                </div>
              </div>
              <div className="text-right">
                <span className="text-xl font-bold font-mono text-amber-600">{lane3Density}%</span>
                <span className="text-[11px] text-studio-muted block font-mono">Avg: 28 km/h</span>
              </div>
            </div>
            <div className="w-full bg-white h-2 rounded-full overflow-hidden border border-studio-pink/30">
              <div className="h-full bg-amber-500 rounded-full" style={{ width: `${lane3Density}%` }} />
            </div>
          </div>
        </div>

        {/* Right 5 cols: AI Recommendation & Action Core */}
        <div className="lg:col-span-5 flex flex-col justify-between space-y-4">
          <div className="p-6 rounded-3xl bg-studio-bgLight/80 border border-studio-pink shadow-sm relative overflow-hidden h-full flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 text-studio-coral font-mono text-xs font-bold tracking-wider uppercase mb-3">
                <Sparkles className="w-4 h-4 text-studio-coral animate-spin" style={{ animationDuration: '6s' }} />
                AI Recommendation Engine
              </div>

              {!isOptimized ? (
                <>
                  <div className="p-4 rounded-2xl bg-red-100/60 border border-red-200 mb-4">
                    <div className="flex items-start gap-2.5">
                      <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <div className="text-sm font-bold text-red-900 font-syne">High Congestion Detected in Lane 01</div>
                        <div className="text-xs text-red-800/80 mt-1 leading-relaxed font-grotesk">
                          Vehicle queue exceeds 140m. Webster static cycle causing 4.2 min cumulative delay.
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="p-4 rounded-2xl bg-white border border-studio-pink shadow-sm text-studio-text">
                    <div className="text-xs font-mono text-studio-coral font-bold uppercase">Proposed Intervention</div>
                    <p className="text-base font-extrabold text-studio-text mt-1 font-syne">
                      “Extend green phase for Lane 01 by 18 seconds.”
                    </p>
                    <div className="mt-3 flex items-center gap-4 text-xs font-mono text-studio-muted">
                      <div>EST. QUEUE CLEAR: <span className="text-emerald-600 font-bold">-63%</span></div>
                      <div>CONFIDENCE: <span className="text-studio-coral font-bold">96.4%</span></div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="p-6 rounded-2xl bg-emerald-50 border border-emerald-300 text-center animate-in zoom-in-95 duration-500 shadow-sm">
                  <div className="w-12 h-12 rounded-full bg-emerald-100 border border-emerald-400 flex items-center justify-center mx-auto mb-3">
                    <CheckCircle2 className="w-7 h-7 text-emerald-600" />
                  </div>
                  <h3 className="text-lg font-black text-emerald-900 uppercase tracking-wider font-syne">
                    Traffic Flow Optimized
                  </h3>
                  <p className="text-xs text-emerald-800 mt-1 font-grotesk">
                    Green phase extended by +18s. Lane 01 density successfully dropped from 87% to 24%.
                  </p>
                  <div className="mt-4 pt-3 border-t border-emerald-200 flex justify-around font-mono text-xs text-emerald-900">
                    <div>THROUGHPUT: <span className="font-bold">+42%</span></div>
                    <div>AVG WAIT: <span className="font-bold">14s (↓68%)</span></div>
                  </div>
                </div>
              )}
            </div>

            {/* Interactive Apply Button */}
            <div className="pt-6">
              {!isOptimized ? (
                <button
                  onClick={handleApplyRecommendation}
                  disabled={isApplying}
                  className="w-full bg-studio-black hover:bg-slate-900 text-white py-4 rounded-full text-xs font-black tracking-widest uppercase flex items-center justify-center gap-2 group shadow-orb transition-all hover:scale-[1.02]"
                >
                  {isApplying ? (
                    <span className="flex items-center gap-2 font-mono">
                      <Zap className="w-4 h-4 text-studio-coral animate-bounce" />
                      DISPATCHING MARL ACTUATOR ({countdown}s)...
                    </span>
                  ) : (
                    <>
                      <span>Apply AI Recommendation</span>
                      <ArrowRight className="w-4 h-4 text-studio-coral group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </button>
              ) : (
                <div className="text-center text-xs font-mono text-emerald-700 flex items-center justify-center gap-2 font-bold">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span>Cycle Synced with Regional MARL Network</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Closed-loop Pipeline Flow */}
      <div className="pt-4 border-t border-studio-pink/30 flex flex-wrap items-center justify-between text-xs font-mono text-studio-muted gap-2">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-studio-coral" />
          <span className="text-studio-text font-bold">Autonomous Closed-Loop Pipeline:</span>
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
          <span className="px-2.5 py-1 bg-studio-coral text-white font-bold rounded-full shadow-sm">5. Actuator Signal</span>
        </div>
      </div>
    </div>
  );
};
