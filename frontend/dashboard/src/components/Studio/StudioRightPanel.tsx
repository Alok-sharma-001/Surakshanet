import React from 'react';
import { ArrowUpRight } from 'lucide-react';

interface Props {
  onOpenCommand: () => void;
  activeProjectIndex: number;
  onSelectProject: (idx: number) => void;
}

export const StudioRightPanel: React.FC<Props> = ({
  onOpenCommand,
  activeProjectIndex,
  onSelectProject,
}) => {
  return (
    <aside className="w-full md:w-44 lg:w-48 bg-white rounded-3xl p-5 shadow-studio-card flex flex-col justify-between items-center border border-studio-pink/30 flex-shrink-0 relative overflow-hidden group">
      {/* Top action */}
      <button
        onClick={onOpenCommand}
        className="w-full text-center group/btn"
      >
        <div className="flex items-center justify-center gap-1 text-[11px] font-mono font-semibold tracking-wider text-studio-text hover:text-studio-coral transition-colors uppercase">
          <span>Launch AI Deck</span>
          <ArrowUpRight className="w-3.5 h-3.5 group-hover/btn:translate-x-0.5 group-hover/btn:-translate-y-0.5 transition-transform" />
        </div>
      </button>

      {/* Centerpiece: Vertical Pedestal with Glossy Black Chrome Spheres */}
      <div 
        onClick={onOpenCommand}
        className="my-auto py-6 flex flex-col items-center justify-center cursor-pointer w-full"
      >
        {/* Glowing textured pedestal background */}
        <div className="relative w-28 h-56 flex flex-col items-center justify-center">
          {/* Subtle coral ambient glow */}
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-studio-coral/25 to-transparent rounded-full blur-xl" />

          {/* Sphere 1 (Top) */}
          <div className="relative w-14 h-14 rounded-full bg-gradient-to-br from-[#2A2B32] via-[#0D0E11] to-black shadow-orb flex items-center justify-center transform -translate-y-2 group-hover:scale-105 transition-transform duration-300">
            {/* White Specular highlights */}
            <span className="absolute top-2.5 left-3 w-3 h-3 rounded-full bg-white opacity-95 blur-[0.3px]" />
            <span className="absolute top-5 left-2 w-1.5 h-1.5 rounded-full bg-white opacity-80" />
            <span className="absolute bottom-2.5 right-3 w-1.5 h-1.5 rounded-full bg-white opacity-60" />
          </div>

          {/* Sphere 2 (Center - Main) */}
          <div className="relative w-16 h-16 rounded-full bg-gradient-to-br from-[#2A2B32] via-[#0D0E11] to-black shadow-orb flex items-center justify-center z-10 group-hover:scale-110 transition-transform duration-300">
            {/* White Specular highlights */}
            <span className="absolute top-3 left-3.5 w-3.5 h-3.5 rounded-full bg-white opacity-95 blur-[0.3px]" />
            <span className="absolute top-6 left-2.5 w-1.5 h-1.5 rounded-full bg-white opacity-80" />
            <span className="absolute bottom-3 right-3.5 w-2 h-2 rounded-full bg-white opacity-70" />
          </div>

          {/* Sphere 3 (Bottom) */}
          <div className="relative w-14 h-14 rounded-full bg-gradient-to-br from-[#2A2B32] via-[#0D0E11] to-black shadow-orb flex items-center justify-center transform translate-y-2 group-hover:scale-105 transition-transform duration-300">
            {/* White Specular highlights */}
            <span className="absolute top-2.5 left-3 w-3 h-3 rounded-full bg-white opacity-95 blur-[0.3px]" />
            <span className="absolute top-5 left-2 w-1.5 h-1.5 rounded-full bg-white opacity-80" />
            <span className="absolute bottom-2.5 right-3 w-1.5 h-1.5 rounded-full bg-white opacity-60" />
          </div>
        </div>

        <div className="text-[10px] font-mono text-studio-muted uppercase tracking-widest mt-2">
          Interactive Ops
        </div>
      </div>

      {/* Bottom Pagination / Ticks Indicator */}
      <div className="flex items-center justify-center gap-3 pt-2">
        {[0, 1, 2, 3].map((idx) => (
          <button
            key={idx}
            onClick={() => onSelectProject(idx)}
            className="flex items-center gap-1 group/tick py-1"
          >
            <span className={`w-0.5 transition-all ${
              activeProjectIndex === idx ? 'h-4 bg-studio-coral font-bold' : 'h-2.5 bg-studio-pink group-hover/tick:h-3.5'
            }`} />
            {activeProjectIndex === idx && (
              <span className="w-1.5 h-1.5 rounded-full bg-studio-coral" />
            )}
          </button>
        ))}
      </div>
    </aside>
  );
};
