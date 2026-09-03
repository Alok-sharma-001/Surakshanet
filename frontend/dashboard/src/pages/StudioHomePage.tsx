import React, { useState, useEffect } from 'react';
import { Studio3DSphere } from '../components/Studio/Studio3DSphere';
import { StudioRightTotem3D } from '../components/Studio/StudioRightTotem3D';
import { ArrowUpRight, ArrowRight, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

/* ────────────────────────────────────────────────────────────
   Project carousel data (SurakshaNet flavored)
   ──────────────────────────────────────────────────────────── */
const PROJECTS = [
  {
    numLeft: '06',
    numRight: '04',
    title: 'Discover Our\nNew Projects\nfrom ©2025',
    concept: 'Validation of Autonomous Ideas\nFrom Concept to POC,\nRapidly',
    tag: '* Exclusive Prototyping\n   bringing visions to life in record time',
    stats: '39.4% Delay Reduction',
  },
  {
    numLeft: '01',
    numRight: '08',
    title: 'Edge Vision\nInfrastructure\nfrom ©2025',
    concept: 'Neural Vision Pipeline\nFor Connected Metropolitan\nCorridors',
    tag: '* Sub-20ms Detection\n   real-time multi-lane classification',
    stats: '99.2% Detection Precision',
  },
  {
    numLeft: '03',
    numRight: '12',
    title: 'Emergency Priority\nProtocol\nfrom ©2025',
    concept: 'Zero-Latency Pre-Emption\nFor Ambulances &\nFirst Responders',
    tag: '* Life-Critical Dispatch\n   automatic 24-signal green wave',
    stats: '58% Transit Acceleration',
  },
  {
    numLeft: '05',
    numRight: '16',
    title: 'Metropolitan\nUrban Grid\nfrom ©2025',
    concept: 'Intelligent Transport Systems\nDesigned for Smart Cities\nWorldwide',
    tag: '* 150 Interconnected Nodes\n   dynamic predictive routing matrix',
    stats: '150 Connected Intersections',
  },
];

/* ────────────────────────────────────────────────────────────
   SVG decorative constellation lines + starburst
   (matching the thin dotted lines with node-dots from reference)
   ──────────────────────────────────────────────────────────── */
const ConstellationSVG: React.FC = () => (
  <svg
    className="absolute inset-0 w-full h-full pointer-events-none z-[5]"
    viewBox="0 0 1520 900"
    preserveAspectRatio="xMidYMid slice"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Primary constellation from starburst to lower-right */}
    <line x1="310" y1="72" x2="420" y2="140" stroke="#B54840" strokeWidth="0.5" strokeDasharray="2,6" opacity="0.3" />
    <line x1="420" y1="140" x2="530" y2="105" stroke="#B54840" strokeWidth="0.5" strokeDasharray="2,6" opacity="0.28" />
    <line x1="530" y1="105" x2="590" y2="170" stroke="#B54840" strokeWidth="0.5" strokeDasharray="2,6" opacity="0.22" />
    <line x1="590" y1="170" x2="680" y2="135" stroke="#B54840" strokeWidth="0.5" strokeDasharray="2,6" opacity="0.18" />

    {/* Upper-left constellation */}
    <line x1="180" y1="55" x2="260" y2="40" stroke="#B54840" strokeWidth="0.4" strokeDasharray="2,5" opacity="0.2" />
    <line x1="260" y1="40" x2="310" y2="72" stroke="#B54840" strokeWidth="0.4" strokeDasharray="2,5" opacity="0.2" />

    {/* Right-side constellation */}
    <line x1="1050" y1="180" x2="1140" y2="240" stroke="#C45A52" strokeWidth="0.4" strokeDasharray="2,5" opacity="0.15" />
    <line x1="1140" y1="240" x2="1210" y2="210" stroke="#C45A52" strokeWidth="0.4" strokeDasharray="2,5" opacity="0.12" />

    {/* Node dots at constellation vertices */}
    <circle cx="310" cy="72" r="3" fill="#B54840" opacity="0.4" />
    <circle cx="420" cy="140" r="2" fill="#B54840" opacity="0.3" />
    <circle cx="530" cy="105" r="2.5" fill="#B54840" opacity="0.25" />
    <circle cx="590" cy="170" r="1.5" fill="#B54840" opacity="0.2" />
    <circle cx="680" cy="135" r="2" fill="#B54840" opacity="0.15" />
    <circle cx="180" cy="55" r="2" fill="#B54840" opacity="0.2" />
    <circle cx="260" cy="40" r="1.5" fill="#B54840" opacity="0.2" />
    <circle cx="1050" cy="180" r="2" fill="#C45A52" opacity="0.15" />
    <circle cx="1140" cy="240" r="2.5" fill="#C45A52" opacity="0.12" />
    <circle cx="1210" cy="210" r="1.5" fill="#C45A52" opacity="0.1" />

    {/* 8-spoke geometric starburst ✻ near the logo area */}
    <g transform="translate(310, 72)" opacity="0.35">
      {[0, 22.5, 45, 67.5, 90, 112.5, 135, 157.5].map((a) => (
        <line
          key={a}
          x1="0" y1="-7" x2="0" y2="7"
          stroke="#9B3228"
          strokeWidth="0.6"
          transform={`rotate(${a})`}
        />
      ))}
    </g>
  </svg>
);

/* ────────────────────────────────────────────────────────────
   MAIN PAGE
   ──────────────────────────────────────────────────────────── */
export const StudioHomePage: React.FC = () => {
  const [activeIdx, setActiveIdx] = useState(0);
  const [fade, setFade] = useState(false);
  const navigate = useNavigate();
  const p = PROJECTS[activeIdx];

  const goNext = () => {
    if (fade) return;
    setFade(true);
    setTimeout(() => {
      setActiveIdx((i) => (i + 1) % PROJECTS.length);
      setFade(false);
    }, 280);
  };
  const goTo = (i: number) => {
    if (fade || i === activeIdx) return;
    setFade(true);
    setTimeout(() => {
      setActiveIdx(i);
      setFade(false);
    }, 280);
  };

  // Live clock
  const [time, setTime] = useState('');
  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="h-screen w-screen bg-[#ECC8C0] flex items-center justify-center p-3 sm:p-5 font-syne select-none overflow-hidden">
      
      {/* ═══════ OUTER BEZEL CONTAINER ═══════ */}
      <div
        className="w-full max-w-[1520px] h-[96vh] min-h-[640px] rounded-[2rem] relative overflow-hidden flex flex-col"
        style={{
          background: 'linear-gradient(165deg, #FBEFEC 0%, #F5DDD8 35%, #F0D2CC 65%, #E8C0B8 100%)',
          boxShadow: '0 50px 120px -25px rgba(160,50,40,0.18), inset 0 0 0 1px rgba(255,255,255,0.65), 0 0 0 1px rgba(180,60,50,0.06)',
        }}
      >

        {/* Constellation overlay */}
        <ConstellationSVG />

        {/* Ambient gradient blurs */}
        <div className="absolute top-[30%] left-[35%] w-[600px] h-[600px] bg-[#E5584D]/[0.07] rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-0 right-[20%] w-[500px] h-[400px] bg-[#D8A8A0]/[0.15] rounded-full blur-[100px] pointer-events-none" />

        {/* ═════════════════════════════════════
            TOP ROW: Numerals + Logo + Title
            ═════════════════════════════════════ */}
        <div className="relative z-20 px-8 sm:px-12 lg:px-14 pt-8 sm:pt-10 flex items-start justify-between">

          {/* LEFT: Giant "06" + ✻ Studio One.Zer° */}
          <div className="flex items-start gap-4 sm:gap-7">
            <span
              className={`text-[5rem] sm:text-[6.5rem] md:text-[8rem] font-[200] tracking-[-0.05em] leading-[0.85] transition-all duration-400 ${fade ? 'opacity-0 -translate-y-3' : 'opacity-100'}`}
              style={{ color: 'rgba(255,255,255,0.7)' }}
            >
              {p.numLeft}
            </span>

            <div className="pt-2 sm:pt-4">
              <div className="flex items-start gap-2">
                <span className="text-xl text-[#B54840] font-serif leading-none mt-1">✻</span>
                <div className="leading-[1.1]">
                  <div className="text-[17px] sm:text-[19px] font-semibold tracking-tight text-[#221E1E]">Studio</div>
                  <div className="text-[17px] sm:text-[19px] font-extrabold tracking-tight text-[#8B2E25]">One.Zer°</div>
                </div>
              </div>
              <p className={`mt-2.5 text-[10px] text-[#221E1E]/50 font-grotesk leading-[1.55] max-w-[185px] whitespace-pre-line transition-opacity duration-400 ${fade ? 'opacity-0' : 'opacity-100'}`}>
                {p.concept}
              </p>
            </div>
          </div>

          {/* RIGHT: Title Block + Giant "04" */}
          <div className="flex items-start gap-3 sm:gap-5">
            <div className={`max-w-[180px] pt-2 sm:pt-4 text-right transition-all duration-400 ${fade ? 'opacity-0 translate-y-3' : 'opacity-100'}`}>
              <h2 className="text-[13px] sm:text-[15px] font-bold text-[#8B2E25] leading-[1.35] whitespace-pre-line">
                {p.title}
              </h2>
            </div>
            <span
              className={`text-[5rem] sm:text-[6.5rem] md:text-[8rem] font-[200] tracking-[-0.05em] leading-[0.85] transition-all duration-400 ${fade ? 'opacity-0 translate-y-3' : 'opacity-100'}`}
              style={{ color: 'rgba(255,255,255,0.7)' }}
            >
              {p.numRight}
            </span>
          </div>
        </div>

        {/* ═════════════════════════════════════
            MIDDLE: Left Tag + 3D Sphere + Right Panel
            ═════════════════════════════════════ */}
        <div className="relative flex-1 flex items-stretch z-10 px-5 sm:px-8 lg:px-10 min-h-0">

          {/* Left margin text */}
          <div className="hidden lg:flex flex-col justify-center w-[170px] flex-shrink-0 pr-3">
            <p className={`text-[10px] font-grotesk text-[#221E1E]/45 leading-[1.6] whitespace-pre-line transition-opacity duration-400 ${fade ? 'opacity-0' : 'opacity-100'}`}>
              {p.tag}
            </p>
            <div className="mt-6 space-y-2.5">
              <button
                onClick={() => navigate('/app')}
                className="flex items-center gap-1.5 text-[10px] font-bold text-[#B54840] hover:text-[#8B2E25] transition-colors group tracking-wide"
              >
                Enter Operations
                <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
              </button>
              <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/50 border border-white/60 text-[8px] font-mono text-[#B54840] font-semibold transition-all duration-400 ${fade ? 'opacity-0' : 'opacity-100'}`}>
                <span className="w-1 h-1 rounded-full bg-[#D04A40]" />
                {p.stats}
              </div>
            </div>
          </div>

          {/* Center: 3D sculpture (fills remaining space) */}
          <div className="flex-1 relative min-w-0 min-h-0">
            <Studio3DSphere />
          </div>

          {/* ═══════ RIGHT WHITE PANEL ═══════
              Reference: white rounded card, "Request A Prototype" top,
              3 glossy black spheres TOUCHING/OVERLAPPING slightly,
              pagination ticks at bottom
          */}
          <aside
            className="hidden md:flex flex-col w-[150px] lg:w-[170px] bg-white rounded-[1.5rem] ml-3 flex-shrink-0 overflow-hidden relative group"
            style={{
              boxShadow: '0 35px 80px -15px rgba(160,50,40,0.1), inset 0 0 0 1px rgba(255,255,255,0.9)',
            }}
          >
            {/* Top: Request A Prototype */}
            <button
              onClick={() => navigate('/app')}
              className="px-4 pt-4 pb-2 text-left group/btn"
            >
              <span className="text-[9px] font-mono font-semibold tracking-[0.08em] text-[#221E1E]/70 hover:text-[#B54840] transition-colors flex items-center gap-1 uppercase leading-tight">
                Request A Prototype
                <ArrowUpRight className="w-3 h-3 text-[#B54840] group-hover/btn:translate-x-0.5 group-hover/btn:-translate-y-0.5 transition-transform" />
              </span>
            </button>

            <div className="mx-4 h-px bg-[#F0D8D4]" />

            {/* Stacked Glossy Black Spheres — touching/overlapping */}
            {/* Continuous Rotating 3D Totem (Matching image 1 media_1788377992336.png) */}
            <div
              onClick={() => navigate('/app')}
              className="flex-1 flex flex-col items-center justify-center cursor-pointer py-1 overflow-hidden"
              title="Click to Enter SurakshaNet Ops"
            >
              <StudioRightTotem3D />
              <span className="mt-1 text-[8px] font-mono text-[#8A7A78] uppercase tracking-[0.12em] font-semibold">
                Interactive Ops
              </span>
            </div>

            <div className="mx-4 h-px bg-[#F0D8D4]" />

            {/* Pagination ticks */}
            <div className="px-4 py-3 flex items-center justify-center gap-2.5">
              {PROJECTS.map((_, i) => (
                <button
                  key={i}
                  onClick={() => goTo(i)}
                  className="flex flex-col items-center py-0.5"
                  aria-label={`Project ${i + 1}`}
                >
                  <span
                    className={`w-[1.5px] rounded-full transition-all duration-300 ${
                      activeIdx === i
                        ? 'h-[18px] bg-[#B54840]'
                        : 'h-[10px] bg-[#E0C0BA] hover:h-[14px] hover:bg-[#D09890]'
                    }`}
                  />
                  {activeIdx === i && (
                    <span className="w-[4px] h-[4px] rounded-full bg-[#B54840] mt-[3px]" />
                  )}
                </button>
              ))}
            </div>
          </aside>
        </div>

        {/* ═════════════════════════════════════
            BOTTOM STRIP (darker blush tint at bottom edge)
            ═════════════════════════════════════ */}
        <div
          className="relative z-20 px-8 sm:px-12 lg:px-14 pb-5 sm:pb-7 pt-3 flex flex-col sm:flex-row items-center justify-between gap-2.5"
          style={{
            background: 'linear-gradient(to bottom, transparent, rgba(210,140,130,0.12))',
          }}
        >
          {/* Left: System indicator */}
          <div className="flex items-center gap-2.5 text-[9px] font-mono text-[#221E1E]/60 tracking-[0.05em]">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#B54840] opacity-40" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#B54840]" />
            </span>
            <span className="font-bold">AI SYSTEM: ACTIVE</span>
            <span className="text-[#B54840]/30">•</span>
            <span>150 NODES</span>
            <span className="text-[#B54840]/30">•</span>
            <span>{time}</span>
          </div>

          {/* Right: Action Buttons */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={goNext}
              className="px-3.5 py-1.5 rounded-full bg-white/70 backdrop-blur-sm hover:bg-white text-[9px] font-bold text-[#221E1E] border border-white/60 shadow-sm flex items-center gap-1.5 transition-all hover:shadow-md tracking-wide"
            >
              Next Innovation
              <ChevronRight className="w-3 h-3" />
            </button>

            <button
              onClick={() => navigate('/app')}
              className="px-4 py-2 rounded-full bg-[#B54840] hover:bg-[#8B2E25] text-white text-[9px] font-bold shadow-[0_6px_20px_-4px_rgba(181,72,64,0.4)] flex items-center gap-1.5 transition-all hover:scale-[1.03] tracking-wide"
            >
              Launch SurakshaNet Ops
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
