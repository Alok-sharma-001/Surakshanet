import { Server } from 'lucide-react';
import { TelemetrySourceBadge } from '../components/TelemetrySourceBadge';

// SN-012g/§13.10: this page previously rendered six hardcoded mock devices
// with fabricated GPU temp/FPS/memory/uplink numbers, a header claiming
// "150 Total / 142 Online / 5 Warning / 3 Offline" (numbers that didn't even
// match the 6 devices actually shown), and "Restart"/"View Logs" buttons
// with no onClick handler at all — clicking them did nothing. There is no
// edge/Jetson hardware anywhere in this project's architecture (see
// CLAUDE.md §2/§3) for this page to report on.
export default function EdgeDevicesPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col">
        <h1 className="text-2xl font-bold text-slate-900">Edge Devices</h1>
        <p className="text-sm text-slate-500">Jetson Fleet Management</p>
      </div>

      <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm px-6 py-16 flex flex-col items-center justify-center gap-3 text-center">
        <Server className="w-8 h-8 text-slate-300" />
        <TelemetrySourceBadge source={null} />
        <p className="text-sm text-slate-500 max-w-sm">
          No edge compute devices are deployed for this project. This page
          will list real device telemetry once an edge fleet exists to report it.
        </p>
      </div>
    </div>
  );
}
