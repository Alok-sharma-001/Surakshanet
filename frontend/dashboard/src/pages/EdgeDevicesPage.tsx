import { Server, RotateCw, FileText } from 'lucide-react';
import clsx from 'clsx';

type DeviceStatus = 'online' | 'warning' | 'offline';

interface EdgeDevice {
  id: string;
  location: string;
  status: DeviceStatus;
  gpuTemp: number;
  fps: number;
  memoryUsage: number;
  uplinkSpeed: number;
}

const mockDevices: EdgeDevice[] = [
  { id: 'BLR-NODE-8821', location: 'MG Road Junction', status: 'online', gpuTemp: 65, fps: 28, memoryUsage: 64, uplinkSpeed: 45 },
  { id: 'BLR-NODE-8822', location: 'Brigade Road', status: 'warning', gpuTemp: 82, fps: 15, memoryUsage: 88, uplinkSpeed: 12 },
  { id: 'BLR-NODE-8823', location: 'Indiranagar 100ft', status: 'online', gpuTemp: 58, fps: 30, memoryUsage: 45, uplinkSpeed: 55 },
  { id: 'BLR-NODE-8824', location: 'Koramangala 80ft', status: 'offline', gpuTemp: 0, fps: 0, memoryUsage: 0, uplinkSpeed: 0 },
  { id: 'BLR-NODE-8825', location: 'HSR Layout', status: 'online', gpuTemp: 70, fps: 29, memoryUsage: 72, uplinkSpeed: 38 },
  { id: 'BLR-NODE-8826', location: 'Silk Board', status: 'warning', gpuTemp: 85, fps: 12, memoryUsage: 92, uplinkSpeed: 8 },
];

export default function EdgeDevicesPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col">
        <h1 className="text-2xl font-bold text-slate-900">Edge Devices</h1>
        <p className="text-sm text-slate-500">Jetson Fleet Management</p>
      </div>

      <div className="flex flex-wrap gap-4 items-center bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-4">
        <div className="flex items-center gap-2 border-r border-slate-200 pr-4">
          <Server className="w-5 h-5 text-slate-500" />
          <span className="text-sm font-semibold text-slate-700">150 Total</span>
        </div>
        <div className="flex items-center gap-2 border-r border-slate-200 pr-4">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500"></div>
          <span className="text-sm font-medium text-slate-700">142 Online</span>
        </div>
        <div className="flex items-center gap-2 border-r border-slate-200 pr-4">
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500"></div>
          <span className="text-sm font-medium text-slate-700">5 Warning</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500"></div>
          <span className="text-sm font-medium text-slate-700">3 Offline</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {mockDevices.map((device) => (
          <div key={device.id} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-5 flex flex-col">
            <div className="flex justify-between items-start mb-4">
              <div>
                <div className="font-mono text-sm font-bold text-slate-900">{device.id}</div>
                <div className="text-sm text-slate-500 mt-1">{device.location}</div>
              </div>
              <span className={clsx(
                "px-2.5 py-1 text-xs font-semibold rounded-full",
                device.status === 'online' && "bg-emerald-100 text-emerald-700",
                device.status === 'warning' && "bg-yellow-100 text-yellow-700",
                device.status === 'offline' && "bg-red-100 text-red-700"
              )}>
                {device.status.charAt(0).toUpperCase() + device.status.slice(1)}
              </span>
            </div>

            <div className="space-y-4 mb-6 flex-1">
              <div>
                <div className="flex justify-between text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
                  <span>GPU Temp</span>
                  <span>{device.status === 'offline' ? '--' : `${device.gpuTemp}°C`}</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-1.5">
                  <div 
                    className={clsx(
                      "h-1.5 rounded-full",
                      device.gpuTemp < 75 ? "bg-emerald-500" : (device.gpuTemp < 85 ? "bg-yellow-500" : "bg-red-500")
                    )}
                    style={{ width: `${Math.min(device.gpuTemp, 100)}%` }}
                  ></div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">FPS</div>
                  <div className="font-mono font-medium text-slate-900">{device.status === 'offline' ? '--' : device.fps}</div>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Memory</div>
                  <div className="font-mono font-medium text-slate-900">{device.status === 'offline' ? '--' : `${device.memoryUsage}%`}</div>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Uplink</div>
                  <div className="font-mono font-medium text-slate-900">{device.status === 'offline' ? '--' : `${device.uplinkSpeed}M`}</div>
                </div>
              </div>
            </div>

            <div className="flex gap-3 mt-auto">
              <button className="flex-1 flex items-center justify-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg px-4 py-2 text-sm font-medium transition-colors">
                <RotateCw className="w-4 h-4" />
                Restart
              </button>
              <button className="flex-1 flex items-center justify-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg px-4 py-2 text-sm font-medium transition-colors">
                <FileText className="w-4 h-4" />
                View Logs
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
