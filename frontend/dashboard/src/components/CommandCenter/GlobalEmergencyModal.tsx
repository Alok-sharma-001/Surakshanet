import React, { useState } from 'react';
import { AlertTriangle, X, Siren, Radio, ShieldAlert } from 'lucide-react';
import { toast } from 'react-hot-toast';
import clsx from 'clsx';
import { api } from '../../services/api';

interface GlobalEmergencyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type EmergencyAction = 'green_corridor' | 'all_red' | null;

// SN-012g/§13.10: "Confirm & Activate" previously did nothing but
// `setTimeout(() => setIsActivated(true), 1500)` for either option, then
// claimed "All 24 signals along the corridor have been pre-empted" or "All
// intersections in the network are now holding red" — a global, header-level
// emergency control that made zero API calls. Green Corridor now calls the
// real POST /emergency/activate (the same endpoint EmergencyPage uses).
// All-Red Hold has no backend endpoint anywhere in this project — there's no
// citywide all-red action to call — so it's disabled with an honest reason
// rather than faked.
const GlobalEmergencyModal: React.FC<GlobalEmergencyModalProps> = ({ isOpen, onClose }) => {
  const [selectedAction, setSelectedAction] = useState<EmergencyAction>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isActivated, setIsActivated] = useState(false);

  if (!isOpen) return null;

  const handleActivate = async () => {
    if (selectedAction !== 'green_corridor') return;
    setIsConfirming(true);
    try {
      await api.emergency.activate({
        priority: 'CRITICAL',
        vehicle_type: 'AMBULANCE',
        route_junction_ids: ['J0', 'J1', 'J2', 'J3'],
        corridor: ['J0', 'J1', 'J2', 'J3'],
      });
      setIsActivated(true);
    } catch (err) {
      toast.error('Could not activate the green corridor — backend call failed.');
    } finally {
      setIsConfirming(false);
    }
  };

  const handleReset = () => {
    setSelectedAction(null);
    setIsActivated(false);
    setIsConfirming(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-red-50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-100 rounded-xl">
              <ShieldAlert className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Emergency Override</h2>
              <p className="text-xs text-slate-500">Auth Level: ADMIN — Critical Actions</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-red-100 transition-colors">
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          {isActivated ? (
            <div className="text-center py-6 space-y-3">
              <div className="w-16 h-16 mx-auto rounded-full bg-emerald-100 flex items-center justify-center">
                <Radio className="w-8 h-8 text-emerald-600 animate-pulse" />
              </div>
              <h3 className="text-lg font-bold text-emerald-700">Green Corridor Activated</h3>
              <p className="text-sm text-slate-500">
                Preemption requested for junctions J0-J3. Check the Emergency page for corridor status.
              </p>
              <button
                onClick={handleReset}
                className="mt-4 px-6 py-2.5 bg-slate-100 hover:bg-slate-200 rounded-xl text-sm font-semibold text-slate-700 transition-colors"
              >
                Dismiss
              </button>
            </div>
          ) : (
            <>
              <p className="text-sm text-slate-600">
                Select an emergency action to override normal traffic signal operations.
              </p>

              {/* Action Cards */}
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setSelectedAction('green_corridor')}
                  className={clsx(
                    'p-4 rounded-xl border-2 text-left transition-all',
                    selectedAction === 'green_corridor'
                      ? 'border-teal-500 bg-teal-50 shadow-sm'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  )}
                >
                  <Siren className={clsx('w-6 h-6 mb-2', selectedAction === 'green_corridor' ? 'text-teal-600' : 'text-slate-400')} />
                  <div className="text-sm font-bold text-slate-800">Green Corridor</div>
                  <div className="text-xs text-slate-500 mt-1">Pre-empt signals along emergency route</div>
                </button>

                <button
                  disabled
                  title="No citywide all-red endpoint exists on the backend yet"
                  className="p-4 rounded-xl border-2 text-left transition-all border-slate-100 bg-slate-50 cursor-not-allowed opacity-60"
                >
                  <AlertTriangle className="w-6 h-6 mb-2 text-slate-300" />
                  <div className="text-sm font-bold text-slate-400">All-Red Hold</div>
                  <div className="text-xs text-slate-400 mt-1">Not implemented — no backend endpoint</div>
                </button>
              </div>

              {/* Warning */}
              {selectedAction && (
                <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-xl">
                  <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-amber-800">
                    <span className="font-bold">Caution:</span> This action will call the real emergency
                    preemption endpoint for junctions J0-J3. Requires ADMIN authorization.
                  </p>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={onClose}
                  className="flex-1 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 rounded-xl text-sm font-semibold text-slate-600 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleActivate}
                  disabled={selectedAction !== 'green_corridor' || isConfirming}
                  className={clsx(
                    'flex-1 px-4 py-2.5 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2',
                    selectedAction === 'green_corridor'
                      ? 'bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/25'
                      : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  )}
                >
                  {isConfirming ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Activating...
                    </>
                  ) : (
                    'Confirm & Activate'
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default GlobalEmergencyModal;
