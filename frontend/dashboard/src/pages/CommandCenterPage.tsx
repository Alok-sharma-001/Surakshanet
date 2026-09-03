import React, { useState } from 'react';
import { Navbar, CommandTab } from '../components/CommandCenter/Navbar';
import { AIInsightsTicker } from '../components/CommandCenter/AIInsightsTicker';
import { CityTrafficCanvas, IntersectionData } from '../components/CommandCenter/CityTrafficCanvas';
import { IntersectionModal } from '../components/CommandCenter/IntersectionModal';
import { SignalControlInteractive } from '../components/CommandCenter/SignalControlInteractive';
import { ComputerVisionFeed } from '../components/CommandCenter/ComputerVisionFeed';
import { LiveIncidents } from '../components/CommandCenter/LiveIncidents';
import { AnalyticsDashboard } from '../components/CommandCenter/AnalyticsDashboard';
import { Map, SlidersHorizontal } from 'lucide-react';

export const CommandCenterPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<CommandTab>('overview');
  const [selectedIntersection, setSelectedIntersection] = useState<IntersectionData | null>(null);
  const [isOptimized, setIsOptimized] = useState<boolean>(false);

  const handleSelectIntersection = (node: IntersectionData) => {
    setSelectedIntersection(node);
  };

  const handleQuickOptimize = (id: string) => {
    setIsOptimized(true);
    if (id === 'A-102') {
      setActiveTab('signal-control');
    }
  };

  return (
    <div className="min-h-screen bg-studio-bg text-studio-text flex flex-col font-syne selection:bg-studio-coral selection:text-white">
      {/* Top Studio Cyber Navbar */}
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Live AI Intelligence Ticker in Studio Theme */}
      <div className="max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <AIInsightsTicker />
      </div>

      {/* Main Content Viewport */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Tab 1: Overview Deck */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* The Core Showcase Feature Front & Center */}
            <div>
              <div className="flex items-center justify-between mb-3 px-1">
                <h3 className="text-xs font-mono font-bold text-studio-coralDark uppercase tracking-wider flex items-center gap-2">
                  <SlidersHorizontal className="w-3.5 h-3.5 text-studio-coral" />
                  Primary Showcase: Closed-Loop AI Signal Optimization
                </h3>
                <span className="text-[11px] font-mono text-studio-muted font-bold">DEMO INTERACTION READY</span>
              </div>
              <SignalControlInteractive onOptimizedStateChange={setIsOptimized} />
            </div>

            {/* Split Row: Live Traffic Map + Computer Vision */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Left 7 cols: Interactive City Grid */}
              <div className="lg:col-span-7 bg-white rounded-3xl p-6 border border-studio-pink/40 shadow-studio-card flex flex-col justify-between">
                <div className="flex items-center justify-between pb-4 border-b border-studio-pink/30 mb-4">
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-studio-text uppercase">
                    <Map className="w-4 h-4 text-studio-coral" />
                    <span>Metropolitan Traffic Density Matrix</span>
                  </div>
                  <button
                    onClick={() => setActiveTab('live-map')}
                    className="text-xs font-grotesk font-bold text-studio-coral hover:text-studio-coralDark hover:underline"
                  >
                    Expand Full Map →
                  </button>
                </div>
                <div className="h-[400px] relative">
                  <CityTrafficCanvas
                    onSelectIntersection={handleSelectIntersection}
                    selectedId={selectedIntersection?.id || 'A-102'}
                    isOptimized={isOptimized}
                  />
                  {selectedIntersection && (
                    <IntersectionModal
                      intersection={selectedIntersection}
                      onClose={() => setSelectedIntersection(null)}
                      onQuickOptimize={handleQuickOptimize}
                      isOptimized={isOptimized}
                    />
                  )}
                </div>
              </div>

              {/* Right 5 cols: Computer Vision Feed Preview */}
              <div className="lg:col-span-5 flex flex-col">
                <ComputerVisionFeed />
              </div>
            </div>

            {/* Incidents & Analytics Teaser Row */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              <div className="lg:col-span-7">
                <LiveIncidents />
              </div>
              <div className="lg:col-span-5">
                <AnalyticsDashboard />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Live Map View */}
        {activeTab === 'live-map' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-2">
              <div>
                <h2 className="text-2xl font-black text-studio-text">Live Metropolitan Traffic Map</h2>
                <p className="text-xs font-grotesk text-studio-muted">
                  Select any intersection or lane to view real-time density, camera feeds, and signal cycles.
                </p>
              </div>
            </div>

            <div className="h-[680px] relative bg-white rounded-3xl p-4 border border-studio-pink/40 shadow-studio-card">
              <CityTrafficCanvas
                onSelectIntersection={handleSelectIntersection}
                selectedId={selectedIntersection?.id || 'A-102'}
                isOptimized={isOptimized}
              />
              {selectedIntersection && (
                <IntersectionModal
                  intersection={selectedIntersection}
                  onClose={() => setSelectedIntersection(null)}
                  onQuickOptimize={handleQuickOptimize}
                  isOptimized={isOptimized}
                />
              )}
            </div>
          </div>
        )}

        {/* Tab 3: Traffic AI (Computer Vision) */}
        {activeTab === 'traffic-ai' && (
          <div className="space-y-6">
            <ComputerVisionFeed />
          </div>
        )}

        {/* Tab 4: Signal Control (Interactive Simulation) */}
        {activeTab === 'signal-control' && (
          <div className="space-y-6">
            <SignalControlInteractive onOptimizedStateChange={setIsOptimized} />
          </div>
        )}

        {/* Tab 5: Live Incidents */}
        {activeTab === 'incidents' && (
          <div className="space-y-6">
            <LiveIncidents />
          </div>
        )}

        {/* Tab 6: Analytics */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <AnalyticsDashboard />
          </div>
        )}
      </main>
    </div>
  );
};
