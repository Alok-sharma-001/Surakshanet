import React from 'react';
import { AlertTriangle, Info, Bell, CheckCircle2 } from 'lucide-react';
import { Card } from '../../components/common/Card';
import { StatusBadge } from '../../components/common/StatusBadge';

const mockAlerts = [
  { id: 1, type: 'Congestion', severity: 'CRITICAL', jct: 'City Center Junction', msg: 'Queue length exceeded 250m. Possible gridlock.', time: '2 mins ago', ack: false },
  { id: 2, type: 'Hardware', severity: 'WARNING', jct: 'Phool Bagh Junction', msg: 'Camera sensor 2 offline. Degraded detection.', time: '15 mins ago', ack: false },
  { id: 3, type: 'System', severity: 'INFO', jct: 'All', msg: 'Model retraining completed successfully.', time: '1 hour ago', ack: true },
];

export const AlertsPage: React.FC = () => {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">System Alerts</h1>
        <div className="flex gap-3">
          <select className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white">
            <option>All Severities</option>
            <option>Critical Only</option>
          </select>
          <select className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white">
            <option>Unacknowledged</option>
            <option>All Alerts</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="bg-red-50 border-red-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-100 rounded-full text-red-600"><AlertTriangle size={24} /></div>
            <div>
              <p className="text-sm font-medium text-red-800">Critical Alerts</p>
              <p className="text-2xl font-bold text-red-900">3</p>
            </div>
          </div>
        </Card>
        <Card className="bg-yellow-50 border-yellow-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-yellow-100 rounded-full text-yellow-600"><Bell size={24} /></div>
            <div>
              <p className="text-sm font-medium text-yellow-800">Unacknowledged</p>
              <p className="text-2xl font-bold text-yellow-900">12</p>
            </div>
          </div>
        </Card>
        <Card className="bg-blue-50 border-blue-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-100 rounded-full text-blue-600"><Info size={24} /></div>
            <div>
              <p className="text-sm font-medium text-blue-800">Total Today</p>
              <p className="text-2xl font-bold text-blue-900">45</p>
            </div>
          </div>
        </Card>
      </div>

      <Card title="Recent Alerts">
        <div className="space-y-3">
          {mockAlerts.map(alert => (
            <div 
              key={alert.id} 
              className={`p-4 rounded-lg border flex gap-4 items-start ${
                alert.severity === 'CRITICAL' ? 'border-l-4 border-l-red-500 bg-red-50/30' : 
                alert.severity === 'WARNING' ? 'border-l-4 border-l-yellow-500 bg-yellow-50/30' : 'border-gray-200'
              }`}
            >
              <div className={`mt-1 ${alert.severity === 'CRITICAL' ? 'text-red-500' : alert.severity === 'WARNING' ? 'text-yellow-500' : 'text-blue-500'}`}>
                {alert.severity === 'CRITICAL' ? <AlertTriangle size={20} /> : alert.severity === 'WARNING' ? <Bell size={20} /> : <Info size={20} />}
              </div>
              <div className="flex-grow">
                <div className="flex justify-between items-start mb-1">
                  <div className="flex items-center gap-2">
                    <h4 className="font-bold text-gray-900">{alert.jct}</h4>
                    <StatusBadge status={alert.type} variant="default" />
                  </div>
                  <span className="text-xs text-gray-500">{alert.time}</span>
                </div>
                <p className="text-gray-600 text-sm">{alert.msg}</p>
              </div>
              {!alert.ack && (
                <button className="flex items-center gap-1 px-3 py-1.5 bg-white border border-gray-300 rounded hover:bg-gray-50 text-sm font-medium text-gray-700 transition-colors">
                  <CheckCircle2 size={16} className="text-green-600" /> Ack
                </button>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

export default AlertsPage;
