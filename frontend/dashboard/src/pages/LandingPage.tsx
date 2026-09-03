import { useNavigate } from 'react-router-dom';
import { 
  Shield, 
  ArrowRight, 
  Eye, 
  Sliders, 
  Activity,
  ChevronRight
} from 'lucide-react';
import { CityTrafficCanvas } from '../components/CommandCenter/CityTrafficCanvas';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-dark-primary text-slate-100 selection:bg-cyan selection:text-black relative overflow-x-hidden">
      {/* Ambient glowing radial gradients */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-gradient-to-b from-cyan-500/10 via-blue-600/5 to-transparent blur-3xl pointer-events-none" />

      {/* Top Floating Navbar */}
      <header className="relative z-50 max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/30 border border-cyan-500/40 flex items-center justify-center shadow-cyan-sm">
            <Shield className="w-5 h-5 text-cyan" />
          </div>
          <div>
            <span className="text-xl font-black tracking-tight text-white">
              Suraksha<span className="text-cyan">Net</span>
            </span>
            <span className="text-[10px] font-mono text-slate-400 block tracking-widest uppercase">
              SMART CITY AI OPS
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/command')}
            className="btn-cyan flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider"
          >
            <span>Launch Command Center</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="text-center max-w-3xl mx-auto mb-12">
          {/* Eyebrow badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-dark-elevated/80 border border-cyan-500/30 text-xs font-mono font-semibold text-cyan mb-6 shadow-cyan-sm">
            <span className="w-2 h-2 rounded-full bg-cyan animate-ping" />
            <span>AI-POWERED INTELLIGENT TRAFFIC & ROAD SAFETY NETWORK</span>
          </div>

          {/* Main Headline */}
          <h1 className="text-4xl sm:text-6xl md:text-7xl font-black text-white tracking-tight leading-[1.08] mb-6">
            See Traffic. <br />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-400">
              Predict Problems.
            </span> <br />
            Move Smarter.
          </h1>

          {/* Subtitle */}
          <p className="text-base sm:text-lg text-slate-300 leading-relaxed max-w-2xl mx-auto mb-8 font-normal">
            SurakshaNet uses AI-powered computer vision and real-time traffic intelligence to monitor roads, detect incidents, and dynamically optimize traffic signals.
          </p>

          {/* CTA Button Group */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 font-mono">
            <button
              onClick={() => navigate('/command')}
              className="w-full sm:w-auto btn-cyan px-8 py-4 text-sm font-bold uppercase tracking-wider flex items-center justify-center gap-3 group shadow-cyan-glow"
            >
              <span>Launch Command Center</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>

            <a
              href="#network-simulation"
              className="w-full sm:w-auto btn-glass px-8 py-4 text-sm font-semibold uppercase tracking-wider text-slate-300 hover:text-white flex items-center justify-center gap-2"
            >
              <span>Explore SurakshaNet</span>
              <ChevronRight className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Living Smart City Traffic Grid Hero Visualization */}
        <section id="network-simulation" className="mt-8 mb-16">
          <div className="glass-card p-2 sm:p-4 border border-cyan-500/30 shadow-2xl relative">
            <div className="flex items-center justify-between px-4 py-3 border-b border-blue-500/20 mb-3">
              <div className="flex items-center gap-2 text-xs font-mono text-cyan uppercase font-bold">
                <Activity className="w-4 h-4 text-cyan animate-pulse" />
                <span>Simulated Smart-City Transportation Network</span>
              </div>
              <div className="text-xs font-mono text-slate-400">
                CLICK ANY INTERSECTION TO INSPECT
              </div>
            </div>

            {/* Interactive Canvas */}
            <div className="h-[500px]">
              <CityTrafficCanvas />
            </div>
          </div>
        </section>

        {/* Live Network Telemetry KPIs Banner */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 my-16">
          <div className="glass-card p-6 border border-blue-500/20 text-center">
            <div className="text-3xl sm:text-4xl font-black text-white font-mono">150+</div>
            <div className="text-xs font-mono text-cyan uppercase mt-1">Connected Intersections</div>
          </div>

          <div className="glass-card p-6 border border-cyan-500/30 text-center shadow-cyan-sm">
            <div className="text-3xl sm:text-4xl font-black text-cyan font-mono">39.4%</div>
            <div className="text-xs font-mono text-slate-300 uppercase mt-1">Average Delay Reduction</div>
          </div>

          <div className="glass-card p-6 border border-blue-500/20 text-center">
            <div className="text-3xl sm:text-4xl font-black text-white font-mono">99.2%</div>
            <div className="text-xs font-mono text-cyan uppercase mt-1">YOLOv8 Detection Accuracy</div>
          </div>

          <div className="glass-card p-6 border border-blue-500/20 text-center">
            <div className="text-3xl sm:text-4xl font-black text-emerald-400 font-mono">18.4s</div>
            <div className="text-xs font-mono text-slate-300 uppercase mt-1">Green Corridor Response</div>
          </div>
        </div>

        {/* Core Pillars / Features Section */}
        <section className="my-20">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-3xl sm:text-4xl font-black text-white tracking-tight">
              Intelligent Infrastructure for Modern Smart Cities
            </h2>
            <p className="text-sm text-slate-400 mt-3 font-normal">
              From continuous edge computer-vision to reinforcement-learning actuators.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Feature 1: Computer Vision */}
            <div className="glass-card p-8 border border-blue-500/20 hover:border-cyan-500/40 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan mb-6 group-hover:scale-110 transition-transform">
                <Eye className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Computer Vision & YOLO Tracking</h3>
              <p className="text-sm text-slate-400 leading-relaxed">
                Processes high-resolution video streams directly at the edge, categorizing vehicle density, pedestrian crossings, and vehicle classes with sub-20ms latency.
              </p>
            </div>

            {/* Feature 2: MARL Signal Optimization */}
            <div className="glass-card p-8 border border-cyan-500/30 hover:border-cyan-500/60 shadow-cyan-sm transition-all group">
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400 mb-6 group-hover:scale-110 transition-transform">
                <Sliders className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Dynamic AI Signal Optimization</h3>
              <p className="text-sm text-slate-400 leading-relaxed">
                Multi-Agent Reinforcement Learning (MARL) coordinates adjacent intersections in real time, shifting green-phase allocations to alleviate bottleneck lanes before congestion spreads.
              </p>
            </div>

            {/* Feature 3: Road Safety & Incidents */}
            <div className="glass-card p-8 border border-blue-500/20 hover:border-cyan-500/40 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mb-6 group-hover:scale-110 transition-transform">
                <Shield className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Emergency Green Corridors</h3>
              <p className="text-sm text-slate-400 leading-relaxed">
                Automatically identifies approaching ambulances, fire trucks, and police units, pre-clearing 24 consecutive signals along the corridor to decrease transit times by 58%.
              </p>
            </div>
          </div>
        </section>

        {/* Bottom Call to Action Card */}
        <section className="my-16 glass-card p-8 sm:p-12 border border-cyan-500/40 text-center relative overflow-hidden shadow-2xl">
          <div className="relative z-10 max-w-xl mx-auto">
            <h3 className="text-2xl sm:text-3xl font-black text-white mb-3">
              Ready to Experience Next-Gen Traffic Intelligence?
            </h3>
            <p className="text-sm text-slate-300 mb-6 font-normal">
              Step into the operational cockpit and monitor simulated city corridors in real time.
            </p>
            <button
              onClick={() => navigate('/command')}
              className="btn-cyan px-8 py-3.5 text-sm font-mono font-bold uppercase tracking-wider inline-flex items-center gap-2 shadow-cyan-glow"
            >
              <span>Enter Command Center</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-8 text-center text-xs font-mono text-slate-500">
        <p>© 2026 SurakshaNet • Smart City Autonomous Traffic Platform</p>
      </footer>
    </div>
  );
};
