import { useState, useEffect } from 'react';

const LIVE_INSIGHTS = [
  {
    id: 1,
    category: 'CONGESTION SPIKE',
    text: 'Traffic congestion on Ring Road increased by 27% in the last 15 minutes.',
    type: 'warning',
    timestamp: 'Just now',
    impact: 'Signal +12s recommended',
  },
  {
    id: 2,
    category: 'LANE UTILIZATION',
    text: 'Lane 02 (Downtown East) is currently underutilized by 42%.',
    type: 'info',
    timestamp: '1m ago',
    impact: 'Phase reallocation active',
  },
  {
    id: 3,
    category: 'OPTIMIZATION OPPORTUNITY',
    text: 'Recommended signal timing adjustment could reduce average waiting time by 18% on Corridor Alpha.',
    type: 'success',
    timestamp: '3m ago',
    impact: 'High reward expected',
  },
  {
    id: 4,
    category: 'RISK FORECAST',
    text: 'Accident probability elevated near Intersection 07 due to wet pavement friction sensors.',
    type: 'danger',
    timestamp: '5m ago',
    impact: 'VMS speed advisory posted',
  },
];

export const AIInsightsTicker: React.FC = () => {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % LIVE_INSIGHTS.length);
    }, 4500);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="bg-white rounded-2xl p-4 border border-studio-pink/40 shadow-sm relative overflow-hidden font-syne">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Left branding */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="w-8 h-8 rounded-full bg-studio-black shadow-orb flex items-center justify-center">
            <span className="text-studio-coral text-sm font-serif">✻</span>
          </div>
          <div>
            <div className="font-grotesk text-[10px] font-bold text-studio-coral uppercase tracking-wider">
              AI TRAFFIC INTELLIGENCE
            </div>
            <div className="text-xs font-bold text-studio-text">Live Cognitive Stream</div>
          </div>
        </div>

        {/* Center rotating insight */}
        <div className="flex-1 md:mx-6 overflow-hidden">
          <div className="flex items-center gap-3 font-grotesk">
            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase flex-shrink-0 ${
              LIVE_INSIGHTS[currentIndex].type === 'warning'
                ? 'bg-amber-100 text-amber-900 border border-amber-300'
                : LIVE_INSIGHTS[currentIndex].type === 'danger'
                ? 'bg-red-100 text-red-900 border border-red-300'
                : LIVE_INSIGHTS[currentIndex].type === 'success'
                ? 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                : 'bg-studio-bg text-studio-coralDark border border-studio-pink'
            }`}>
              {LIVE_INSIGHTS[currentIndex].category}
            </span>

            <p className="text-xs text-studio-text font-semibold truncate">
              {LIVE_INSIGHTS[currentIndex].text}
            </p>

            <span className="hidden lg:inline text-[11px] font-mono text-studio-coralDark bg-studio-bgLight px-2.5 py-0.5 rounded-full border border-studio-pink/40 flex-shrink-0 font-medium">
              {LIVE_INSIGHTS[currentIndex].impact}
            </span>
          </div>
        </div>

        {/* Right timeline count */}
        <div className="flex items-center gap-2 flex-shrink-0 font-mono text-xs text-studio-muted">
          <span className="w-2 h-2 rounded-full bg-studio-coral animate-ping" />
          <span>{LIVE_INSIGHTS[currentIndex].timestamp}</span>
        </div>
      </div>
    </div>
  );
};
