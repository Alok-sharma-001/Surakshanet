import React, { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';
import { AuditLogItem } from '../types';
import { 
  ShieldAlert, 
  Search, 
  ChevronDown, 
  ChevronRight, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Cpu, 
  User as UserIcon, 
  Server, 
  Info,
  SlidersHorizontal
} from 'lucide-react';
import clsx from 'clsx';

export const AuditPage: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'ADMIN';

  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [samplingNotice, setSamplingNotice] = useState<string>('');

  // Filters
  const [actorTypeFilter, setActorTypeFilter] = useState<string>('');
  const [actionFilter, setActionFilter] = useState<string>('');
  const [resultFilter, setResultFilter] = useState<string>('');
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});

  const fetchAuditLogs = useCallback(async () => {
    if (!isAdmin) return;
    setLoading(true);
    setError(null);
    try {
      const params: any = { limit: 100, offset: 0 };
      if (actorTypeFilter) params.actor_type = actorTypeFilter;
      if (actionFilter) params.action = actionFilter.trim();
      if (resultFilter) params.result = resultFilter;

      const res = await api.audit.getAll(params);
      const data = res.data;
      setLogs(data.items || []);
      setTotalCount(data.total || 0);
      setSamplingNotice(data.sampling_notice || '');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to retrieve audit records.');
    } finally {
      setLoading(false);
    }
  }, [isAdmin, actorTypeFilter, actionFilter, resultFilter]);

  useEffect(() => {
    fetchAuditLogs();
  }, [fetchAuditLogs]);

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  if (!isAdmin) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto text-red-600">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-red-900">Access Restricted</h2>
          <p className="text-sm text-red-700 max-w-md mx-auto">
            The Audit Trail viewer is strictly restricted to users with the <span className="font-semibold">ADMIN</span> role. Your current role is <span className="font-mono bg-red-100 px-2 py-0.5 rounded text-red-800">{user?.role || 'ANONYMOUS'}</span>.
          </p>
          <div className="pt-2 text-xs text-red-600 font-mono">
            Every access attempt is recorded with ACCESS_DENIED in the governance audit ledger.
          </div>
        </div>
      </div>
    );
  }

  const getActorBadge = (type: string) => {
    switch (type) {
      case 'AI':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            <Cpu className="w-3.5 h-3.5" /> AI
          </span>
        );
      case 'SYSTEM':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-50 text-slate-700 border border-slate-200">
            <Server className="w-3.5 h-3.5" /> SYSTEM
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <UserIcon className="w-3.5 h-3.5" /> USER
          </span>
        );
    }
  };

  const getResultBadge = (result: string) => {
    switch (result) {
      case 'SUCCESS':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> SUCCESS
          </span>
        );
      case 'DENIED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3 text-amber-600" /> DENIED
          </span>
        );
      case 'FAILURE':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-red-50 text-red-700 border border-red-200">
            <XCircle className="w-3 h-3 text-red-600" /> FAILURE
          </span>
        );
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Audit & Governance Log</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-teal-100 text-teal-800 uppercase tracking-wider">
              Admin Only
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Tamper-evident system activity ledger, operator decisions, and sampled AI control inferences.
          </p>
        </div>

        <button
          onClick={fetchAuditLogs}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-sm font-medium shadow-sm transition-colors"
        >
          <RefreshCw className={clsx("w-4 h-4 text-slate-500", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Sampling Disclosure Banner */}
      <div className="bg-sky-50 border border-sky-200 rounded-xl p-4 flex items-start gap-3">
        <Info className="w-5 h-5 text-sky-600 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-sky-900 leading-relaxed">
          <span className="font-bold">AI Decision Sampling Disclosure (SN-106): </span>
          {samplingNotice || "AI control decisions in this audit ledger are sampled (every safety clamp, mode transition, and fallback, plus 1 in 20 routine cycles). Full un-sampled raw control steps are preserved in control_decisions."}
        </div>
      </div>

      {/* Filters Toolbar */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
        <div className="flex items-center gap-2 text-xs font-bold text-slate-600 uppercase tracking-wider">
          <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
          Filter Audit Records
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {/* Action Search */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter by action..."
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500 focus:bg-white"
            />
          </div>

          {/* Actor Type */}
          <div>
            <select
              value={actorTypeFilter}
              onChange={(e) => setActorTypeFilter(e.target.value)}
              className="w-full px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500 focus:bg-white text-slate-700"
            >
              <option value="">All Actor Types</option>
              <option value="USER">USER (Operators & Admins)</option>
              <option value="AI">AI (DQN, Vision, Anomaly)</option>
              <option value="SYSTEM">SYSTEM (Automated Daemons)</option>
            </select>
          </div>

          {/* Result Filter */}
          <div>
            <select
              value={resultFilter}
              onChange={(e) => setResultFilter(e.target.value)}
              className="w-full px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500 focus:bg-white text-slate-700"
            >
              <option value="">All Results</option>
              <option value="SUCCESS">SUCCESS</option>
              <option value="DENIED">DENIED (403 Rejections)</option>
              <option value="FAILURE">FAILURE</option>
            </select>
          </div>

          <div className="flex items-center justify-end text-xs text-slate-500">
            Showing <span className="font-semibold text-slate-800 mx-1">{logs.length}</span> of <span className="font-semibold text-slate-800 mx-1">{totalCount}</span> records
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-xs p-4 rounded-lg">
          {error}
        </div>
      )}

      {/* Audit Log Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                <th className="py-3 px-4 w-8"></th>
                <th className="py-3 px-4">Timestamp (UTC)</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Target</th>
                <th className="py-3 px-4">Result</th>
                <th className="py-3 px-4">Confidence</th>
                <th className="py-3 px-4">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {loading && logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400 font-sans">
                    Loading audit records...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400 font-sans">
                    No matching audit logs found.
                  </td>
                </tr>
              ) : (
                logs.map((log) => {
                  const isExpanded = !!expandedRows[log.id];
                  return (
                    <React.Fragment key={log.id}>
                      <tr 
                        onClick={() => toggleRow(log.id)}
                        className={clsx(
                          "cursor-pointer hover:bg-slate-50/80 transition-colors",
                          isExpanded && "bg-slate-50/50"
                        )}
                      >
                        <td className="py-3 px-4 text-slate-400">
                          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </td>
                        <td className="py-3 px-4 text-slate-700 whitespace-nowrap">
                          {log.timestamp ? log.timestamp.replace('T', ' ').slice(0, 19) : '-'}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            {getActorBadge(log.actor_type)}
                            {log.actor_id && (
                              <span className="text-[10px] text-slate-400 font-mono" title={log.actor_id}>
                                {log.actor_id.slice(0, 8)}...
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded text-[11px]">
                            {log.action}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-600">
                          {log.target_type ? (
                            <span>
                              <span className="text-slate-400">{log.target_type}:</span>{' '}
                              <span className="font-medium text-slate-700">{log.target_id ? log.target_id.slice(0, 8) + '...' : '-'}</span>
                            </span>
                          ) : (
                            <span className="text-slate-400">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {getResultBadge(log.result)}
                        </td>
                        <td className="py-3 px-4">
                          {log.actor_type === 'AI' && log.confidence != null ? (
                            <span className="px-2 py-0.5 rounded font-bold text-purple-700 bg-purple-50 text-[11px]">
                              {(log.confidence * 100).toFixed(1)}%
                            </span>
                          ) : (
                            <span className="text-slate-300">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-slate-500 text-[11px]">
                          {log.source || 'manual'}
                        </td>
                      </tr>

                      {/* Expandable JSON Detail */}
                      {isExpanded && (
                        <tr className="bg-slate-50/60 font-sans">
                          <td colSpan={8} className="px-8 py-4 border-t border-b border-slate-200">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                              {/* Metadata & Attribution */}
                              <div className="space-y-2">
                                <div className="font-bold text-slate-700 uppercase tracking-wider text-[10px]">
                                  Attribution & Integrity
                                </div>
                                <div className="bg-white p-3 rounded-lg border border-slate-200 font-mono text-[11px] space-y-1">
                                  <div><span className="text-slate-400">Log ID:</span> {log.id}</div>
                                  <div><span className="text-slate-400">Correlation ID:</span> {log.correlation_id || 'none'}</div>
                                  {log.model && <div><span className="text-slate-400">AI Model:</span> {log.model} (v{log.model_version || '1.0'})</div>}
                                  {log.actor_id && <div><span className="text-slate-400">Actor UUID:</span> {log.actor_id}</div>}
                                  {log.target_id && <div><span className="text-slate-400">Target UUID:</span> {log.target_id}</div>}
                                </div>
                              </div>

                              {/* Input Payload */}
                              <div className="space-y-2">
                                <div className="font-bold text-slate-700 uppercase tracking-wider text-[10px]">
                                  Input Parameters (Credentials Redacted)
                                </div>
                                <pre className="bg-white p-3 rounded-lg border border-slate-200 text-slate-800 text-[11px] max-h-40 overflow-y-auto font-mono">
                                  {JSON.stringify(log.input, null, 2) || '{}'}
                                </pre>
                              </div>

                              {/* Output Payload */}
                              <div className="md:col-span-2 space-y-2">
                                <div className="font-bold text-slate-700 uppercase tracking-wider text-[10px]">
                                  Output / Action Consequence
                                </div>
                                <pre className="bg-white p-3 rounded-lg border border-slate-200 text-slate-800 text-[11px] max-h-48 overflow-y-auto font-mono">
                                  {JSON.stringify(log.output, null, 2) || '{}'}
                                </pre>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default AuditPage;
