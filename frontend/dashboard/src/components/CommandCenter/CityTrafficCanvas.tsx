import React, { useEffect, useRef, useState } from 'react';

export interface IntersectionData {
  id: string;
  name: string;
  x: number;
  y: number;
  level: 'CRITICAL' | 'MODERATE' | 'SMOOTH';
  vehicles: number;
  speed: number;
  cycle: number;
  aiStatus: 'OPTIMIZING' | 'ACTIVE' | 'STANDBY';
  lanes: {
    id: string;
    traffic: number;
    signal: 'RED' | 'YELLOW' | 'GREEN';
  }[];
}

export const INITIAL_INTERSECTIONS: IntersectionData[] = [
  {
    id: 'A-102',
    name: 'Intersection A-102 (Downtown Hub)',
    x: 350,
    y: 220,
    level: 'CRITICAL',
    vehicles: 1284,
    speed: 18,
    cycle: 120,
    aiStatus: 'OPTIMIZING',
    lanes: [
      { id: 'Lane 01 (North)', traffic: 87, signal: 'RED' },
      { id: 'Lane 02 (East)', traffic: 32, signal: 'GREEN' },
      { id: 'Lane 03 (South)', traffic: 61, signal: 'YELLOW' },
    ],
  },
  {
    id: 'B-007',
    name: 'Intersection 07 (Ring Road Expressway)',
    x: 680,
    y: 180,
    level: 'MODERATE',
    vehicles: 890,
    speed: 34,
    cycle: 90,
    aiStatus: 'ACTIVE',
    lanes: [
      { id: 'Lane 01', traffic: 45, signal: 'GREEN' },
      { id: 'Lane 02', traffic: 58, signal: 'GREEN' },
      { id: 'Lane 03', traffic: 30, signal: 'RED' },
    ],
  },
  {
    id: 'C-042',
    name: 'MG Boulevard - Cyber Junction',
    x: 480,
    y: 420,
    level: 'SMOOTH',
    vehicles: 620,
    speed: 48,
    cycle: 75,
    aiStatus: 'ACTIVE',
    lanes: [
      { id: 'Lane 01', traffic: 22, signal: 'GREEN' },
      { id: 'Lane 02', traffic: 28, signal: 'GREEN' },
    ],
  },
  {
    id: 'D-114',
    name: 'NH-52 Sarita Expressway Corridor',
    x: 820,
    y: 380,
    level: 'CRITICAL',
    vehicles: 1450,
    speed: 14,
    cycle: 135,
    aiStatus: 'OPTIMIZING',
    lanes: [
      { id: 'Lane 01', traffic: 92, signal: 'RED' },
      { id: 'Lane 02', traffic: 40, signal: 'GREEN' },
    ],
  },
  {
    id: 'E-019',
    name: 'Sector 4 Tech Corridor',
    x: 180,
    y: 360,
    level: 'SMOOTH',
    vehicles: 410,
    speed: 52,
    cycle: 60,
    aiStatus: 'ACTIVE',
    lanes: [
      { id: 'Lane 01', traffic: 18, signal: 'GREEN' },
      { id: 'Lane 02', traffic: 20, signal: 'GREEN' },
    ],
  },
];

interface Props {
  onSelectIntersection?: (intersection: IntersectionData) => void;
  selectedId?: string;
  isOptimized?: boolean;
}

export const CityTrafficCanvas: React.FC<Props> = ({
  onSelectIntersection,
  selectedId = 'A-102',
  isOptimized = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // Vehicle particle structure
  const vehiclesRef = useRef<Array<{
    x: number;
    y: number;
    targetX: number;
    targetY: number;
    speed: number;
    color: string;
    progress: number;
    roadIndex: number;
  }>>([]);

  // Roads definition (connecting intersections and edges)
  const roads = [
    { from: [50, 220], to: [350, 220], color: isOptimized ? '#22C55E' : '#EF4444', label: 'Lane 01 (Heavy)' },
    { from: [350, 220], to: [680, 180], color: '#F59E0B', label: 'Lane 02 (Moderate)' },
    { from: [680, 180], to: [980, 180], color: '#22C55E', label: 'Lane 03 (Smooth)' },
    { from: [350, 220], to: [480, 420], color: isOptimized ? '#22C55E' : '#F59E0B', label: 'Connector' },
    { from: [480, 420], to: [820, 380], color: '#EF4444', label: 'Highway West' },
    { from: [180, 360], to: [350, 220], color: '#22C55E', label: 'Sector 4 Link' },
    { from: [180, 360], to: [480, 420], color: '#22C55E', label: 'Tech Bypass' },
    { from: [680, 180], to: [820, 380], color: '#3B82F6', label: 'Eastern Expressway' },
  ];

  // Initialize vehicles
  useEffect(() => {
    const list = [];
    for (let i = 0; i < 48; i++) {
      const roadIdx = i % roads.length;
      const road = roads[roadIdx];
      const p = Math.random();
      list.push({
        x: road.from[0] + (road.to[0] - road.from[0]) * p,
        y: road.from[1] + (road.to[1] - road.from[1]) * p,
        targetX: road.to[0],
        targetY: road.to[1],
        speed: (roadIdx === 0 && !isOptimized) ? 0.002 : (0.004 + Math.random() * 0.005),
        color: (roadIdx === 0 && !isOptimized) ? '#EF4444' : '#00D9FF',
        progress: p,
        roadIndex: roadIdx,
      });
    }
    vehiclesRef.current = list;
  }, [isOptimized]);

  // Animation Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      // Background clear: Soft warm blush/peach
      ctx.fillStyle = '#FDF2EF';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Studio subtle grid
      ctx.strokeStyle = 'rgba(230, 88, 77, 0.08)';
      ctx.lineWidth = 1;
      const gridSize = 40;
      for (let x = 0; x < canvas.width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = 0; y < canvas.height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Draw Roads
      roads.forEach((road) => {
        // Base white road casing with soft shadow
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 20;
        ctx.lineCap = 'round';
        ctx.shadowColor = 'rgba(230, 88, 77, 0.08)';
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.moveTo(road.from[0], road.from[1]);
        ctx.lineTo(road.to[0], road.to[1]);
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Inner glowing lane
        ctx.strokeStyle = road.color;
        ctx.lineWidth = 4;
        ctx.shadowColor = road.color;
        ctx.shadowBlur = 6;
        ctx.beginPath();
        ctx.moveTo(road.from[0], road.from[1]);
        ctx.lineTo(road.to[0], road.to[1]);
        ctx.stroke();
        ctx.shadowBlur = 0; // reset
      });

      // Update & Draw Vehicles (Glossy Obsidian Black Orbs)
      vehiclesRef.current.forEach((veh) => {
        veh.progress += veh.speed;
        if (veh.progress >= 1) {
          veh.progress = 0;
        }
        const road = roads[veh.roadIndex];
        veh.x = road.from[0] + (road.to[0] - road.from[0]) * veh.progress;
        veh.y = road.from[1] + (road.to[1] - road.from[1]) * veh.progress;

        // Glossy black vehicle orb
        ctx.fillStyle = '#0D0E11';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
        ctx.shadowBlur = 5;
        ctx.beginPath();
        ctx.arc(veh.x, veh.y, 4, 0, Math.PI * 2);
        ctx.fill();

        // White Specular Highlight on vehicle
        ctx.fillStyle = '#FFFFFF';
        ctx.beginPath();
        ctx.arc(veh.x - 1, veh.y - 1, 1.2, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      // Draw Intersections
      INITIAL_INTERSECTIONS.forEach((node) => {
        const isSelected = node.id === selectedId;
        const isHovered = node.id === hoveredId;

        let nodeColor = '#22C55E';
        if (node.level === 'CRITICAL') nodeColor = isOptimized && node.id === 'A-102' ? '#22C55E' : '#E5584D';
        else if (node.level === 'MODERATE') nodeColor = '#F59E0B';

        // Outer pulsing ring
        ctx.strokeStyle = nodeColor;
        ctx.lineWidth = isSelected ? 3 : 1.5;
        ctx.shadowColor = nodeColor;
        ctx.shadowBlur = isSelected ? 16 : 8;
        ctx.beginPath();
        ctx.arc(node.x, node.y, isSelected ? 18 : 13, 0, Math.PI * 2);
        ctx.stroke();

        // Inner solid glossy black core
        ctx.fillStyle = '#0D0E11';
        ctx.beginPath();
        ctx.arc(node.x, node.y, isSelected ? 7 : 5, 0, Math.PI * 2);
        ctx.fill();

        // Specular dot
        ctx.fillStyle = '#FFFFFF';
        ctx.beginPath();
        ctx.arc(node.x - 1.5, node.y - 1.5, 1.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;

        // Label box
        ctx.font = '700 11px "Space Grotesk", sans-serif';
        ctx.fillStyle = isSelected || isHovered ? '#B9362C' : '#5A4E4D';
        ctx.fillText(node.id, node.x - 14, node.y - (isSelected ? 24 : 18));
      });

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [selectedId, hoveredId, isOptimized]);

  // Click handler
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = ((e.clientX - rect.left) / rect.width) * 1050;
    const y = ((e.clientY - rect.top) / rect.height) * 550;

    const clicked = INITIAL_INTERSECTIONS.find((node) => {
      const dist = Math.hypot(node.x - x, node.y - y);
      return dist < 30;
    });

    if (clicked && onSelectIntersection) {
      onSelectIntersection(clicked);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = ((e.clientX - rect.left) / rect.width) * 1050;
    const y = ((e.clientY - rect.top) / rect.height) * 550;

    const hovered = INITIAL_INTERSECTIONS.find((node) => {
      const dist = Math.hypot(node.x - x, node.y - y);
      return dist < 30;
    });

    setHoveredId(hovered ? hovered.id : null);
  };

  return (
    <div className="relative w-full h-full min-h-[480px] bg-studio-bgLight rounded-2xl overflow-hidden border border-studio-pink/50 shadow-sm flex items-center justify-center font-grotesk">
      <canvas
        ref={canvasRef}
        width={1050}
        height={550}
        onClick={handleCanvasClick}
        onMouseMove={handleMouseMove}
        className="w-full h-full object-contain cursor-crosshair"
      />

      {/* Map Legend Overlay in White Studio Glass */}
      <div className="absolute top-4 left-4 bg-white/95 backdrop-blur-md rounded-2xl p-4 text-xs flex flex-col gap-2 pointer-events-none border border-studio-pink/40 shadow-sm">
        <div className="flex items-center gap-2 font-mono text-studio-coral font-bold uppercase tracking-wider text-[10px]">
          <span className="w-2 h-2 rounded-full bg-studio-coral animate-ping" />
          Live Network Grid (City Scale)
        </div>
        <div className="flex items-center gap-4 text-studio-text font-semibold pt-1">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-studio-coral" />
            <span>Heavy (Lane 1)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
            <span>Moderate (Lane 2)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span>Smooth (Lane 3)</span>
          </div>
        </div>
      </div>

      {/* Telemetry HUD corner */}
      <div className="absolute bottom-4 right-4 bg-white/95 backdrop-blur-md px-4 py-2.5 rounded-xl text-xs font-mono text-studio-muted pointer-events-none border border-studio-pink/40 shadow-sm">
        <div>COORDINATES: <span className="text-studio-coral font-bold">28.6139° N, 77.2090° E</span></div>
        <div>CONNECTED NODES: <span className="text-emerald-700 font-bold">150/150 ONLINE</span></div>
      </div>
    </div>
  );
};
