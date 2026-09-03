import { Settings, Bell, Code, Monitor, AlertTriangle } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto w-full">
      <div className="flex flex-col">
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500">System Configuration</p>
      </div>

      <div className="space-y-6">
        {/* General Settings */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
            <Settings className="w-5 h-5 text-slate-500" />
            <h2 className="text-base font-semibold text-slate-800">General</h2>
          </div>
          <div className="px-6 py-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">System Name</label>
              <input type="text" className="w-full border border-slate-200 rounded-lg px-4 py-3 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500" defaultValue="Surakshanet Production" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Timezone</label>
                <select className="w-full border border-slate-200 rounded-lg px-4 py-3 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500">
                  <option>Asia/Kolkata (UTC+5:30)</option>
                  <option>UTC</option>
                  <option>America/New_York (UTC-5:00)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Language</label>
                <select className="w-full border border-slate-200 rounded-lg px-4 py-3 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500">
                  <option>English (UK)</option>
                  <option>English (US)</option>
                  <option>Hindi</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
            <Bell className="w-5 h-5 text-slate-500" />
            <h2 className="text-base font-semibold text-slate-800">Notifications</h2>
          </div>
          <div className="px-6 py-5 space-y-4">
            {['Email alerts', 'SMS alerts', 'Dashboard alerts', 'Sound effects'].map((item, idx) => (
              <div key={idx} className="flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700">{item}</span>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" defaultChecked={idx !== 1} />
                  <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-600"></div>
                </label>
              </div>
            ))}
          </div>
        </div>

        {/* API Configuration */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
            <Code className="w-5 h-5 text-slate-500" />
            <h2 className="text-base font-semibold text-slate-800">API Configuration</h2>
          </div>
          <div className="px-6 py-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">API Endpoint</label>
              <div className="font-mono text-sm bg-slate-50 p-3 rounded-lg border border-slate-200 text-slate-700">https://api.surakshanet.gov.in/v2</div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
              <div className="flex gap-2">
                <input type="password" value="sk-live-1234567890abcdef" readOnly className="font-mono flex-1 border border-slate-200 rounded-lg px-4 py-3 bg-slate-50 text-sm focus:outline-none text-slate-700" />
                <button className="bg-sky-600 hover:bg-sky-700 text-white rounded-lg px-4 py-2 font-medium transition-colors">Regenerate</button>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Refresh Interval</label>
              <select className="w-full border border-slate-200 rounded-lg px-4 py-3 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500">
                <option>Every 5 seconds</option>
                <option>Every 30 seconds</option>
                <option>Every 1 minute</option>
                <option>Manual only</option>
              </select>
            </div>
          </div>
        </div>

        {/* Display */}
        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
            <Monitor className="w-5 h-5 text-slate-500" />
            <h2 className="text-base font-semibold text-slate-800">Display</h2>
          </div>
          <div className="px-6 py-5 space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Theme</label>
                <select className="w-full border border-slate-200 rounded-lg px-4 py-3 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500">
                  <option>Light</option>
                  <option>Dark</option>
                  <option>System</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Map Default Zoom</label>
                <select className="w-full border border-slate-200 rounded-lg px-4 py-3 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500">
                  <option>12x (City Level)</option>
                  <option>15x (District Level)</option>
                  <option>18x (Street Level)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Units</label>
                <select className="w-full border border-slate-200 rounded-lg px-4 py-3 bg-white text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500">
                  <option>Metric (km, °C)</option>
                  <option>Imperial (mi, °F)</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Danger Zone */}
        <div className="bg-red-50 rounded-xl border border-red-200 shadow-sm">
          <div className="px-6 py-4 border-b border-red-100 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <h2 className="text-base font-semibold text-red-800">Danger Zone</h2>
          </div>
          <div className="px-6 py-5 flex items-center gap-4">
            <button className="bg-white border border-red-200 text-red-700 hover:bg-red-50 rounded-lg px-4 py-2.5 font-medium transition-colors">
              Reset to Defaults
            </button>
            <button className="bg-red-600 hover:bg-red-700 text-white rounded-lg px-4 py-2.5 font-medium transition-colors">
              Clear All Data
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
