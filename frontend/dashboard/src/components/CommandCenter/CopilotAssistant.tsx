import React, { useState } from 'react';
import { 
  Bot, 
  Send, 
  Sparkles, 
  ChevronDown, 
  ChevronUp, 
  Activity, 
  Camera, 
  CheckCircle2, 
  Loader2
} from 'lucide-react';
import { api } from '../../services/api';
import toast from 'react-hot-toast';

interface ChatMessage {
  id: string;
  sender: 'operator' | 'agent';
  text: string;
  thoughts?: string;
  timestamp: string;
  status?: 'success' | 'fallback';
}

export const CopilotAssistant: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'agent',
      text: 'Welcome to the Surakshanet TOC Autonomous Copilot. Powered by Google Antigravity SDK and Gemini. I can coordinate multi-intersection green waves, forecast congestion spillbacks, dispatch roadside VMS notices, or simulate network interventions.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: 'success'
    }
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [targetJunction, setTargetJunction] = useState('j-silkboard');
  const [loading, setLoading] = useState(false);
  const [openThoughts, setOpenThoughts] = useState<Record<string, boolean>>({});

  // Simulation state
  const [simType, setSimType] = useState<'PREEMPT_CORRIDOR' | 'DETOUR_REROUTE'>('PREEMPT_CORRIDOR');
  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState<any>(null);

  // Vision inspection state
  const [imagePath, setImagePath] = useState('/opt/surakshanet/cctv_snapshots/frame_0842.jpg');
  const [visionLoading, setVisionLoading] = useState(false);
  const [visionResult, setVisionResult] = useState<any>(null);

  const toggleThoughts = (id: string) => {
    setOpenThoughts(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleSendMessage = async (queryText?: string) => {
    const textToSend = queryText || inputQuery;
    if (!textToSend.trim() || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'operator',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMsg]);
    setInputQuery('');
    setLoading(true);

    try {
      const res = await api.copilot.chat({
        message: textToSend,
        junction_id: targetJunction || undefined,
        stream: false
      });

      const data = res.data;
      const agentMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: data.response,
        thoughts: data.thoughts,
        status: data.status,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages(prev => [...prev, agentMsg]);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to receive agent response');
      const errorMsg: ChatMessage = {
        id: `agent-err-${Date.now()}`,
        sender: 'agent',
        text: 'Autonomous Copilot fallback: Unable to contact cloud supervisor. Enforcing Webster baseline safety timings.',
        status: 'fallback',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleRunSimulation = async () => {
    setSimLoading(true);
    setSimResult(null);
    try {
      const payload: any = { action_type: simType };
      if (simType === 'PREEMPT_CORRIDOR') {
        payload.corridor_junctions = ['j-silkboard', 'j-koramangala', 'j-mg-road'];
      } else {
        payload.avoid_junctions = ['j-tin-factory'];
      }
      const res = await api.copilot.simulateAction(payload);
      setSimResult(res.data);
      toast.success('Simulation evaluated successfully');
    } catch (err: any) {
      toast.error('Simulation failed to compute');
    } finally {
      setSimLoading(false);
    }
  };

  const handleAnalyzeSnapshot = async () => {
    setVisionLoading(true);
    setVisionResult(null);
    try {
      const res = await api.copilot.analyzeSnapshot({
        image_path: imagePath,
        junction_id: targetJunction
      });
      setVisionResult(res.data);
      toast.success('Multimodal incident diagnosis complete');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Snapshot analysis failed');
    } finally {
      setVisionLoading(false);
    }
  };

  return (
    <div className="space-y-6 font-syne">
      {/* Header Banner */}
      <div className="bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-studio-black text-white flex items-center justify-center shadow-orb flex-shrink-0">
            <Bot className="w-6 h-6 text-studio-coral" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-black text-studio-text">TOC Autonomous Incident Commander</h2>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-studio-coral/10 text-studio-coral border border-studio-coral/30 uppercase">
                Google Antigravity SDK
              </span>
            </div>
            <p className="text-xs font-grotesk text-studio-muted mt-0.5">
              Supervises multi-agent delegation: Emergency Preemption, Arterial Flow Detours, and Roadside VMS Dispatch.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right font-grotesk">
            <span className="text-[10px] font-mono text-studio-muted uppercase tracking-wider block">Context Junction</span>
            <select
              value={targetJunction}
              onChange={e => setTargetJunction(e.target.value)}
              className="text-xs font-bold font-mono bg-studio-bgLight border border-studio-pink/50 rounded-xl px-3 py-1.5 text-studio-text focus:outline-none focus:ring-2 focus:ring-studio-coral/40"
            >
              <option value="j-silkboard">Silk Board Junction (j-silkboard)</option>
              <option value="j-mg-road">MG Road & Brigade (j-mg-road)</option>
              <option value="j-hebbal">Hebbal Flyover (j-hebbal)</option>
              <option value="j-tin-factory">Tin Factory (j-tin-factory)</option>
              <option value="j-marathahalli">Marathahalli Bridge (j-marathahalli)</option>
            </select>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left 8 Cols: Conversational Copilot Thread */}
        <div className="lg:col-span-8 flex flex-col bg-white rounded-3xl border border-studio-pink/40 shadow-studio-card overflow-hidden h-[640px]">
          {/* Thread Header */}
          <div className="px-6 py-4 border-b border-studio-pink/30 flex items-center justify-between bg-studio-bgLight/40">
            <div className="flex items-center gap-2 text-xs font-mono font-bold text-studio-text uppercase">
              <Sparkles className="w-4 h-4 text-studio-coral" />
              <span>Multi-Agent Dialogue & Reasoning Stream</span>
            </div>
            <span className="text-[11px] font-mono text-emerald-600 font-bold flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              COGNITIVE LAYER ACTIVE
            </span>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 font-grotesk">
            {messages.map((m) => {
              const isOperator = m.sender === 'operator';
              return (
                <div
                  key={m.id}
                  className={`flex flex-col ${isOperator ? 'items-end' : 'items-start'}`}
                >
                  <div className="flex items-center gap-2 mb-1 px-1">
                    <span className="text-[10px] font-mono font-bold uppercase text-studio-muted">
                      {isOperator ? 'TOC Operator' : 'Incident Commander (Antigravity)'}
                    </span>
                    <span className="text-[10px] font-mono text-studio-muted/70">{m.timestamp}</span>
                    {m.status === 'fallback' && (
                      <span className="px-2 py-0.2 rounded-full text-[9px] font-mono font-bold bg-amber-100 text-amber-800 border border-amber-300">
                        Webster Fallback
                      </span>
                    )}
                  </div>

                  <div
                    className={`max-w-[88%] rounded-2xl p-4 text-xs leading-relaxed ${
                      isOperator
                        ? 'bg-studio-black text-white rounded-tr-none'
                        : 'bg-studio-bgLight text-studio-text border border-studio-pink/40 rounded-tl-none'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{m.text}</p>

                    {/* Collapsible Model Thoughts */}
                    {m.thoughts && (
                      <div className="mt-3 pt-3 border-t border-studio-pink/30">
                        <button
                          onClick={() => toggleThoughts(m.id)}
                          className="flex items-center gap-1 text-[11px] font-mono font-bold text-studio-coral hover:text-studio-coralDark transition-colors"
                        >
                          <span>{openThoughts[m.id] ? 'Hide Reasoning Steps' : 'Inspect Reasoning Steps (Thoughts)'}</span>
                          {openThoughts[m.id] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>
                        {openThoughts[m.id] && (
                          <pre className="mt-2 p-3 bg-white rounded-xl border border-studio-pink/30 font-mono text-[10px] text-studio-muted whitespace-pre-wrap leading-normal overflow-x-auto max-h-40">
                            {m.thoughts}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {loading && (
              <div className="flex items-center gap-2 p-3 text-xs font-grotesk text-studio-muted italic">
                <Loader2 className="w-4 h-4 text-studio-coral animate-spin" />
                <span>Antigravity Incident Commander delegating to specialized subagents...</span>
              </div>
            )}
          </div>

          {/* Quick Prompts Chips */}
          <div className="px-6 py-2 bg-studio-bgLight/30 border-t border-studio-pink/20 flex items-center gap-2 overflow-x-auto font-grotesk">
            <span className="text-[10px] font-mono text-studio-muted uppercase font-bold flex-shrink-0">Prompts:</span>
            {[
              'Preempt emergency corridor for ambulance Silk Board -> MG Road',
              'Forecast 60m traffic volume and spillback risk for j-silkboard',
              'Accident at Tin Factory: compute optimal detour routing',
              'Dispatch VMS roadside warning for heavy fog ahead'
            ].map((p, i) => (
              <button
                key={i}
                onClick={() => handleSendMessage(p)}
                className="text-[11px] font-medium bg-white hover:bg-studio-coral/10 hover:border-studio-coral/40 text-studio-text px-3 py-1 rounded-full border border-studio-pink/40 whitespace-nowrap transition-colors flex-shrink-0 active:scale-95"
              >
                {p}
              </button>
            ))}
          </div>

          {/* Chat Input Bar */}
          <form
            onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }}
            className="p-4 border-t border-studio-pink/30 bg-white flex items-center gap-3 font-grotesk"
          >
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask Incident Commander or issue arterial command..."
              className="flex-1 text-xs bg-studio-bgLight/70 border border-studio-pink/50 rounded-2xl px-4 py-3 text-studio-text placeholder:text-studio-muted/70 focus:outline-none focus:ring-2 focus:ring-studio-coral/40"
            />
            <button
              type="submit"
              disabled={loading || !inputQuery.trim()}
              className="px-5 py-3 rounded-2xl bg-studio-black text-white text-xs font-bold hover:bg-studio-coral transition-colors flex items-center gap-2 disabled:opacity-50 active:scale-95 shadow-sm"
            >
              <span>Dispatch</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>

        {/* Right 4 Cols: What-If Simulation & Multimodal Vision Inspector */}
        <div className="lg:col-span-4 space-y-6">
          {/* Card 1: Closed-Loop Intervention Simulator */}
          <div className="bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-studio-pink/30">
              <div className="flex items-center gap-2 text-xs font-mono font-bold text-studio-text uppercase">
                <Activity className="w-4 h-4 text-studio-coral" />
                <span>What-If Action Simulator</span>
              </div>
              <span className="text-[10px] font-mono text-studio-muted uppercase font-bold">PRE-CABINET</span>
            </div>

            <div className="space-y-3 font-grotesk text-xs">
              <div>
                <label className="block text-[10px] font-mono font-bold text-studio-muted uppercase mb-1">
                  Intervention Strategy
                </label>
                <select
                  value={simType}
                  onChange={(e: any) => setSimType(e.target.value)}
                  className="w-full text-xs font-bold bg-studio-bgLight border border-studio-pink/50 rounded-xl px-3 py-2 text-studio-text focus:outline-none focus:ring-2 focus:ring-studio-coral/40"
                >
                  <option value="PREEMPT_CORRIDOR">Emergency Green Wave Preemption</option>
                  <option value="DETOUR_REROUTE">Dynamic Congestion Detour Reroute</option>
                </select>
              </div>

              <button
                onClick={handleRunSimulation}
                disabled={simLoading}
                className="w-full py-2.5 rounded-xl bg-studio-black text-white font-bold hover:bg-studio-coral transition-colors flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50"
              >
                {simLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Activity className="w-3.5 h-3.5" />}
                <span>Evaluate in Digital Twin</span>
              </button>

              {simResult && (
                <div className="mt-3 p-3 rounded-2xl bg-studio-bgLight/60 border border-studio-pink/40 font-mono text-[11px] space-y-1.5">
                  <div className="flex items-center justify-between text-emerald-700 font-bold">
                    <span>Validation Status:</span>
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      PASSED
                    </span>
                  </div>
                  {simResult.predicted_delay_reduction_pct && (
                    <div className="flex justify-between text-studio-text">
                      <span>Delay Reduction:</span>
                      <span className="font-bold text-studio-coralDark tabular-nums">-{simResult.predicted_delay_reduction_pct}%</span>
                    </div>
                  )}
                  {simResult.predicted_time_savings_minutes && (
                    <div className="flex justify-between text-studio-text">
                      <span>Travel Time Saved:</span>
                      <span className="font-bold text-emerald-600 tabular-nums">+{simResult.predicted_time_savings_minutes} mins</span>
                    </div>
                  )}
                  <div className="text-[10px] text-studio-muted pt-1 border-t border-studio-pink/20">
                    Webster Interlock: min green &gt;= 10s, yellow &gt;= 3s respected.
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Card 2: Multimodal Camera Vision Inspector */}
          <div className="bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-studio-pink/30">
              <div className="flex items-center gap-2 text-xs font-mono font-bold text-studio-text uppercase">
                <Camera className="w-4 h-4 text-studio-coral" />
                <span>Multimodal CCTV Inspector</span>
              </div>
              <span className="text-[10px] font-mono text-studio-muted uppercase font-bold">Gemini Vision</span>
            </div>

            <div className="space-y-3 font-grotesk text-xs">
              <div>
                <label className="block text-[10px] font-mono font-bold text-studio-muted uppercase mb-1">
                  Camera Snapshot Path / URI
                </label>
                <input
                  type="text"
                  value={imagePath}
                  onChange={e => setImagePath(e.target.value)}
                  className="w-full text-xs font-mono bg-studio-bgLight border border-studio-pink/50 rounded-xl px-3 py-2 text-studio-text focus:outline-none focus:ring-2 focus:ring-studio-coral/40"
                />
              </div>

              <button
                onClick={handleAnalyzeSnapshot}
                disabled={visionLoading}
                className="w-full py-2.5 rounded-xl bg-studio-coral text-white font-bold hover:bg-studio-coralDark transition-colors flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50"
              >
                {visionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />}
                <span>Diagnose Hazards (Pydantic Report)</span>
              </button>

              {visionResult && (
                <div className="mt-3 p-3 rounded-2xl bg-white border border-studio-pink/40 font-mono text-[11px] space-y-1.5">
                  <div className="flex justify-between font-bold">
                    <span>Incident Type:</span>
                    <span className="text-studio-coralDark">{visionResult.incident_type}</span>
                  </div>
                  <div className="flex justify-between text-studio-text">
                    <span>Severity:</span>
                    <span className={`font-bold ${visionResult.severity === 'CRITICAL' ? 'text-red-600' : 'text-emerald-600'}`}>
                      {visionResult.severity}
                    </span>
                  </div>
                  <div className="flex justify-between text-studio-text">
                    <span>Lanes Obstructed:</span>
                    <span className="font-bold tabular-nums">{visionResult.lanes_blocked}</span>
                  </div>
                  <div className="pt-1 border-t border-studio-pink/20 text-[10px] text-studio-muted">
                    <span className="font-bold block text-studio-text">VMS Notice:</span>
                    "{visionResult.recommended_vms_advisory}"
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
