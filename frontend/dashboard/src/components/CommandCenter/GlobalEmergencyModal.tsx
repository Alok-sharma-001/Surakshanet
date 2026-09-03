import React, { useState } from 'react';
import { AlertTriangle, X, Siren, Radio, ShieldAlert } from 'lucide-react';
import clsx from 'clsx';

interface GlobalEmergencyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type EmergencyAction = 'green_corridor' | 'all_red' | null;

const GlobalEmergencyModal: React.FC<GlobalEmergencyModalProps> = ({ isOpen, onClose }) => {
  const [selectedAction, setSelectedAction] = useState<EmergencyAction>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isActivated, setIsActivated] = useState(false);

  if (!isOpen) return null;

  const handleActivate = () => {
    setIsConfirming(true);
    setTimeout(() => {
      setIsActivated(true);
      setIsConfirming(false);
    }, 1500);
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
              <h3 className="text-lg font-bold text-emerald-700">
                {selectedAction === 'green_corridor' ? 'Green Corridor Activated' : 'All-Red Hold Active'}
              </h3>
              <p className="text-sm text-slate-500">
                {selectedAction === 'green_corridor'
                  ? 'All 24 signals along the corridor have been pre-empted. Emergency vehicle tracking is live.'
                  : 'All intersections in the network are now holding red. Manual release required.'}
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
                  onClick={() => setSelectedAction('all_red')}
                  className={clsx(
                    'p-4 rounded-xl border-2 text-left transition-all',
                    selectedAction === 'all_red'
                      ? 'border-red-500 bg-red-50 shadow-sm'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  )}
                >
                  <AlertTriangle className={clsx('w-6 h-6 mb-2', selectedAction === 'all_red' ? 'text-red-600' : 'text-slate-400')} />
                  <div className="text-sm font-bold text-slate-800">All-Red Hold</div>
                  <div className="text-xs text-slate-500 mt-1">Immediately stop all traffic city-wide</div>
                </button>
              </div>

              {/* Warning */}
              {selectedAction && (
                <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-xl">
                  <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-amber-800">
                    <span className="font-bold">Caution:</span> This action will immediately override
                    {selectedAction === 'green_corridor' ? ' 24+ signal controllers along the corridor.' : ' all signal controllers in the network.'}{' '}
                    Requires ADMIN authorization.
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
                  disabled={!selectedAction || isConfirming}
                  className={clsx(
                    'flex-1 px-4 py-2.5 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2',
                    selectedAction
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
