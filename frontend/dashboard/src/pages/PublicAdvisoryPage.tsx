import { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  Clock,
  Navigation,
  Compass,
  RefreshCw,
  Shield
} from 'lucide-react';
import { api } from '../services/api';

interface PublicAdvisory {
  id: string;
  severity: 'LOW' | 'MODERATE' | 'SEVERE';
  headline: string;
  corridor: string;
  window: {
    start: string;
    end: string;
  };
  expected_delay_min: {
    low: number;
    high: number;
  };
  cause: string;
  recommended: string | null;
  leave_before: string | null;
  published_at: string;
}

interface NetworkStatus {
  status: 'normal' | 'advisories_active';
  active_count: number;
  summary: string;
}

export default function PublicAdvisoryPage() {
  const [advisories, setAdvisories] = useState<PublicAdvisory[]>([]);
  const [networkStatus, setNetworkStatus] = useState<NetworkStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchData = useCallback(async (isManual: boolean = false) => {
    if (isManual) setIsRefreshing(true);
    try {
      const [advRes, statusRes] = await Promise.all([
        api.public.getAdvisories(),
        api.public.getStatus(),
      ]);

      if (advRes.data?.advisories) {
        setAdvisories(advRes.data.advisories);
      }
      if (statusRes.data) {
        setNetworkStatus(statusRes.data);
      }
      setLastRefreshed(new Date());
    } catch (err) {
      console.error('Failed to fetch public advisories', err);
    } finally {
      setLoading(false);
      if (isManual) setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    // 60s in-place polling without screen flicker
    const interval = setInterval(() => {
      fetchData(false);
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const formatDateTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoString;
    }
  };

  const formatDateRange = (startIso: string, endIso: string) => {
    try {
      const s = new Date(startIso);
      const e = new Date(endIso);
      const isSameDay = s.toDateString() === e.toDateString();
      const sTime = s.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      const eTime = e.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

      if (isSameDay) {
        const today = new Date().toDateString();
        const tomorrow = new Date(Date.now() + 86400000).toDateString();
        let dayPrefix = s.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
        if (s.toDateString() === today) dayPrefix = 'Today';
        else if (s.toDateString() === tomorrow) dayPrefix = 'Tomorrow';
        return `${dayPrefix}, ${sTime} – ${eTime}`;
      }
      return `${s.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${sTime} – ${e.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${eTime}`;
    } catch {
      return `${startIso} – ${endIso}`;
    }
  };

  const getSeverityTheme = (severity: string) => {
    switch (severity.toUpperCase()) {
      case 'SEVERE':
        return {
          cardBorder: 'border-red-300',
          badgeBg: 'bg-red-600',
          badgeText: 'text-white',
          alertTitle: 'HEAVY TRAFFIC EXPECTED',
          icon: AlertTriangle,
          highlightDelay: 'text-red-700 bg-red-50 border-red-200',
        };
      case 'MODERATE':
        return {
          cardBorder: 'border-amber-300',
          badgeBg: 'bg-amber-500',
          badgeText: 'text-white',
          alertTitle: 'MODERATE DELAYS EXPECTED',
          icon: AlertCircle,
          highlightDelay: 'text-amber-800 bg-amber-50 border-amber-200',
        };
      case 'LOW':
      default:
        return {
          cardBorder: 'border-sky-300',
          badgeBg: 'bg-sky-600',
          badgeText: 'text-white',
          alertTitle: 'MINOR DELAYS EXPECTED',
          icon: Info,
          highlightDelay: 'text-sky-800 bg-sky-50 border-sky-200',
        };
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans flex flex-col antialiased">
      {/* Civic Public Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10 shadow-xs">
        <div className="max-w-xl mx-auto px-4 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-teal-600 flex items-center justify-center text-white shadow-xs">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900 leading-tight">SurakshaNet</h1>
              <p className="text-xs text-slate-500">Live Traffic Advisory</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 border border-emerald-200 rounded-full">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span className="text-[11px] font-semibold text-emerald-800">Live</span>
            </div>
            <button
              onClick={() => fetchData(true)}
              disabled={isRefreshing}
              aria-label="Refresh traffic advisories"
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-teal-600' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-xl w-full mx-auto px-4 py-5 space-y-4">
        {networkStatus && (
          <div className="text-xs font-medium text-slate-600 bg-white border border-slate-200/80 rounded-xl px-3.5 py-2.5 shadow-xs flex items-center justify-between">
            <span>{networkStatus.summary}</span>
            <span className="text-[10px] text-slate-400 shrink-0 ml-2">Citywide</span>
          </div>
        )}

        {loading ? (
          <div className="py-16 text-center space-y-3">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-600 border-t-transparent mx-auto" />
            <p className="text-sm font-medium text-slate-500">Checking corridor status...</p>
          </div>
        ) : advisories.length === 0 ? (
          /* Honest Empty State - SN-066 */
          <div className="bg-white border border-slate-200 rounded-2xl p-8 text-center shadow-xs space-y-4 my-6">
            <div className="w-14 h-14 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mx-auto border border-emerald-100">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-slate-800">No traffic advisories right now.</h2>
              <p className="text-sm text-slate-500 max-w-xs mx-auto">
                All major city corridors are operating normally. Safe travels!
              </p>
            </div>
            <div className="pt-2 text-xs text-slate-400">
              Updated just now · Refreshes automatically every minute
            </div>
          </div>
        ) : (
          /* Advisory Cards - 3-second decision read */
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-500 px-1">
              <span className="font-semibold text-slate-700">
                {advisories.length} Active {advisories.length === 1 ? 'Advisory' : 'Advisories'}
              </span>
              <span>Updated at {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>

            {advisories.map((advisory) => {
              const theme = getSeverityTheme(advisory.severity);
              const SeverityIcon = theme.icon;

              return (
                <article
                  key={advisory.id}
                  className={`bg-white rounded-2xl border-2 ${theme.cardBorder} shadow-sm overflow-hidden transition-all`}
                >
                  {/* Primary Alert Header: Icon + Word */}
                  <div className={`${theme.badgeBg} ${theme.badgeText} px-4 py-2.5 flex items-center justify-between`}>
                    <div className="flex items-center gap-2 font-bold tracking-wide text-xs sm:text-sm uppercase">
                      <SeverityIcon className="w-4 h-4 shrink-0" />
                      <span>{theme.alertTitle}</span>
                    </div>
                    <span className="text-[11px] font-medium opacity-90">
                      {advisory.severity}
                    </span>
                  </div>

                  <div className="p-5 space-y-4">
                    {/* 1. Where & When */}
                    <div>
                      <h2 className="text-xl font-extrabold text-slate-900 leading-tight">
                        {advisory.corridor}
                      </h2>
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 mt-1">
                        <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span>{formatDateRange(advisory.window.start, advisory.window.end)}</span>
                      </div>
                    </div>

                    {/* 2. How Bad & Why */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                      <div className={`p-3 rounded-xl border ${theme.highlightDelay}`}>
                        <div className="text-[11px] font-bold uppercase tracking-wider opacity-75">
                          Expected Delay
                        </div>
                        <div className="text-lg font-black mt-0.5">
                          {advisory.expected_delay_min.low}–{advisory.expected_delay_min.high} minutes
                        </div>
                      </div>

                      <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                        <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                          Cause
                        </div>
                        <div className="text-sm font-semibold text-slate-800 mt-0.5">
                          {advisory.cause}
                        </div>
                      </div>
                    </div>

                    {/* 3. Actionable Advice (What should I do?) */}
                    <div className="space-y-2 pt-2 border-t border-slate-100">
                      {advisory.recommended && (
                        <div className="flex items-start gap-2.5 bg-teal-50/70 border border-teal-200/80 rounded-xl p-3">
                          <Navigation className="w-4 h-4 text-teal-700 mt-0.5 shrink-0" />
                          <div>
                            <span className="text-xs font-bold text-teal-900 uppercase tracking-wide block">
                              Take instead
                            </span>
                            <span className="text-sm font-semibold text-teal-950">
                              {advisory.recommended}
                            </span>
                          </div>
                        </div>
                      )}

                      {advisory.leave_before && (
                        <div className="flex items-start gap-2.5 bg-indigo-50/70 border border-indigo-200/80 rounded-xl p-3">
                          <Compass className="w-4 h-4 text-indigo-700 mt-0.5 shrink-0" />
                          <div>
                            <span className="text-xs font-bold text-indigo-900 uppercase tracking-wide block">
                              Or leave before
                            </span>
                            <span className="text-sm font-semibold text-indigo-950">
                              {formatDateTime(advisory.leave_before)}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </main>

      {/* Civic Footer: Privacy statement & no tracking notice */}
      <footer className="mt-auto border-t border-slate-200 bg-white py-4 px-4 text-center">
        <div className="max-w-xl mx-auto space-y-1">
          <p className="text-xs text-slate-500 font-medium">
            SurakshaNet Citizen Information System
          </p>
          <p className="text-[11px] text-slate-400">
            No cookies, no tracking, no personal data collected. Official municipal traffic advisory.
          </p>
        </div>
      </footer>
    </div>
  );
}
