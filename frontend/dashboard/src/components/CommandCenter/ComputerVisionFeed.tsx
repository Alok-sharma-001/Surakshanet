import { useState, useEffect } from 'react';
import { Camera, ShieldCheck, Crosshair, Cpu } from 'lucide-react';

interface DetectionBox {
  id: string;
  label: string;
  confidence: number;
  color: string;
  top: number;
  left: number;
  width: number;
  height: number;
}

const CAM_FEEDS = [
  { id: 'CAM-01', name: 'Cam 01: North Approach', location: 'Intersection A-102 (Downtown)' },
  { id: 'CAM-02', name: 'Cam 02: Ring Road Flyover', location: 'NH-52 Expressway Hub' },
  { id: 'CAM-03', name: 'Cam 03: Cyber Boulevard', location: 'Sector 4 Junction' },
];

export const ComputerVisionFeed: React.FC = () => {
  const [activeCam, setActiveCam] = useState('CAM-01');
  const [fps, setFps] = useState(30.2);

  // Dynamic subtle jitter for bounding boxes
  const [boxes, setBoxes] = useState<DetectionBox[]>([
    { id: '1', label: 'CAR', confidence: 98, color: '#E5584D', top: 32, left: 24, width: 22, height: 26 },
    { id: '2', label: 'BUS', confidence: 91, color: '#0D0E11', top: 22, left: 58, width: 28, height: 38 },
    { id: '3', label: 'BIKE', confidence: 94, color: '#F59E0B', top: 62, left: 16, width: 14, height: 20 },
    { id: '4', label: 'CAR', confidence: 96, color: '#E5584D', top: 58, left: 42, width: 20, height: 24 },
    { id: '5', label: 'PEDESTRIAN', confidence: 95, color: '#22C55E', top: 48, left: 88, width: 8, height: 22 },
  ]);

  // Subtle live tracking jitter
  useEffect(() => {
    const interval = setInterval(() => {
      setBoxes((prev) =>
        prev.map((b) => ({
          ...b,
          left: Math.max(5, Math.min(85, b.left + (Math.random() * 1 - 0.5))),
          top: Math.max(10, Math.min(75, b.top + (Math.random() * 0.8 - 0.4))),
        }))
      );
      setFps(+(29.8 + Math.random() * 0.8).toFixed(1));
    }, 400);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card relative overflow-hidden flex flex-col font-syne">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-studio-pink/30">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            <span className="font-mono text-xs font-bold text-emerald-700 uppercase tracking-wider">
              AI ANALYSIS ACTIVE
            </span>
            <span className="text-studio-muted">|</span>
            <span className="font-mono text-xs text-studio-muted">YOLOv8s-Traffic-v2</span>
          </div>
          <h3 className="text-xl font-black text-studio-text mt-1 flex items-center gap-2">
            <Camera className="w-5 h-5 text-studio-coral" />
            Computer Vision Telemetry Feed
          </h3>
        </div>

        {/* Camera Selector Buttons */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0 font-grotesk">
          {CAM_FEEDS.map((cam) => (
            <button
              key={cam.id}
              onClick={() => setActiveCam(cam.id)}
              className={`px-3.5 py-1.5 rounded-full text-xs font-bold font-mono transition-all ${
                activeCam === cam.id
                  ? 'bg-studio-coral text-white shadow-sm'
                  : 'bg-studio-bgLight text-studio-text/70 border border-studio-pink/40 hover:text-studio-coral'
              }`}
            >
              {cam.id}
            </button>
          ))}
        </div>
      </div>

      {/* Video Stream Simulation Container */}
      <div className="my-5 relative w-full h-80 sm:h-96 rounded-2xl bg-studio-bgLight overflow-hidden border border-studio-pink/50 shadow-inner group">
        {/* Background stylized perspective */}
        <div className="absolute inset-0 bg-gradient-to-b from-studio-pink/20 via-studio-bg/40 to-white/90 flex items-center justify-center pointer-events-none">
          <div className="w-full h-full opacity-15 bg-[radial-gradient(#e5584d_1px,transparent_1px)] [background-size:24px_24px]" />
          <div className="absolute inset-0 flex justify-center pointer-events-none">
            <div className="w-3/4 h-full border-x-2 border-studio-pink/40 transform perspective-[400px] rotate-x-[35deg] bg-white/40" />
          </div>
        </div>

        {/* Bounding Boxes */}
        {boxes.map((box) => (
          <div
            key={box.id}
            className="absolute transition-all duration-300 pointer-events-none font-grotesk"
            style={{
              top: `${box.top}%`,
              left: `${box.left}%`,
              width: `${box.width}%`,
              height: `${box.height}%`,
            }}
          >
            {/* Box Border */}
            <div
              className="w-full h-full rounded-lg border-2 relative"
              style={{ borderColor: box.color, boxShadow: `0 0 10px ${box.color}30` }}
            >
              {/* Corner tick marks */}
              <div className="absolute -top-1 -left-1 w-2 h-2 border-t-2 border-l-2 border-white" />
              <div className="absolute -top-1 -right-1 w-2 h-2 border-t-2 border-r-2 border-white" />
              <div className="absolute -bottom-1 -left-1 w-2 h-2 border-b-2 border-l-2 border-white" />
              <div className="absolute -bottom-1 -right-1 w-2 h-2 border-b-2 border-r-2 border-white" />

              {/* Tag Label */}
              <div
                className="absolute -top-5 left-0 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider text-white flex items-center gap-1 shadow-sm whitespace-nowrap"
                style={{ backgroundColor: box.color }}
              >
                <span>{box.label}</span>
                <span className="opacity-90">· {box.confidence}%</span>
              </div>
            </div>
          </div>
        ))}

        {/* HUD Camera Overlays */}
        <div className="absolute top-3 left-3 bg-white/95 backdrop-blur-md px-3.5 py-1.5 rounded-full border border-studio-pink/50 text-[11px] font-mono text-studio-text flex items-center gap-2 shadow-sm">
          <span className="w-2 h-2 rounded-full bg-studio-coral animate-pulse" />
          <span className="font-bold">LIVE</span>
          <span className="text-studio-coralDark font-bold">{activeCam}</span>
          <span className="text-studio-muted">•</span>
          <span>4K UHD</span>
        </div>

        <div className="absolute top-3 right-3 bg-white/95 backdrop-blur-md px-3.5 py-1.5 rounded-full border border-studio-pink/50 text-[11px] font-mono text-studio-text flex items-center gap-3 shadow-sm">
          <div>FPS: <span className="text-emerald-700 font-bold">{fps}</span></div>
          <div>LATENCY: <span className="text-studio-coral font-bold">14ms</span></div>
        </div>

        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
          <Crosshair className="w-20 h-20 text-studio-coral" />
        </div>

        {/* Bottom Bar: Detected Classes Bar */}
        <div className="absolute bottom-3 left-3 right-3 bg-white/95 backdrop-blur-md px-4 py-2.5 rounded-2xl border border-studio-pink/50 flex flex-wrap items-center justify-between text-xs font-mono shadow-sm">
          <div className="text-studio-muted flex items-center gap-2 font-semibold">
            <Cpu className="w-3.5 h-3.5 text-studio-coral" />
            <span>CLASSIFICATION BREAKDOWN:</span>
          </div>
          <div className="flex items-center gap-4 text-studio-text font-bold">
            <div>CARS: <span className="text-studio-coral">18</span></div>
            <div>BUSES: <span className="text-slate-800">3</span></div>
            <div>BIKES: <span className="text-amber-600">12</span></div>
            <div>PEDESTRIANS: <span className="text-emerald-600">4</span></div>
          </div>
        </div>
      </div>

      {/* Telemetry Footer */}
      <div className="flex flex-wrap items-center justify-between text-xs text-studio-muted font-mono pt-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>Edge Precision: <strong className="text-studio-text font-bold">99.2% mAP@0.5</strong></span>
        </div>
        <div>
          LOCATION: <span className="text-studio-text font-semibold">New Delhi Central Operations Matrix</span>
        </div>
      </div>
    </div>
  );
};
