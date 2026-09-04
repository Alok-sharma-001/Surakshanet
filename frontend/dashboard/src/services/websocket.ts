type MessageCallback = (data: any) => void;

class WebSocketService {
  private sockets: Map<string, WebSocket> = new Map();
  private callbacks: Map<string, Set<MessageCallback>> = new Map();
  private reconnectTimeouts: Map<string, number> = new Map();
  private pingIntervals: Map<string, number> = new Map();

  connect(channel: string) {
    if (this.sockets.has(channel)) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = window.location.port === '5173'
      ? `ws://${window.location.hostname}:8000/ws/${channel}`
      : `${protocol}//${window.location.host}/ws/${channel}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`[Surakshanet WS] Connected to channel: ${channel} via ${wsUrl}`);
      this.startHeartbeat(channel, ws);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const channelCallbacks = this.callbacks.get(channel);
        if (channelCallbacks) {
          channelCallbacks.forEach(cb => cb(data));
        }
      } catch (e) {
        console.error(`[Surakshanet WS] Failed to parse message on ${channel}:`, e);
      }
    };

    ws.onclose = () => {
      console.log(`[Surakshanet WS] Disconnected: ${channel}. Reconnecting in 2s...`);
      this.sockets.delete(channel);
      this.stopHeartbeat(channel);
      
      // Auto-reconnect with 2s delay
      const timeoutId = window.setTimeout(() => this.connect(channel), 2000);
      this.reconnectTimeouts.set(channel, timeoutId);
    };

    this.sockets.set(channel, ws);
  }

  disconnect(channel: string) {
    const ws = this.sockets.get(channel);
    if (ws) {
      ws.close();
      this.sockets.delete(channel);
    }
    const timeout = this.reconnectTimeouts.get(channel);
    if (timeout) {
      clearTimeout(timeout);
      this.reconnectTimeouts.delete(channel);
    }
    this.stopHeartbeat(channel);
  }

  onMessage(channel: string, callback: MessageCallback) {
    if (!this.callbacks.has(channel)) {
      this.callbacks.set(channel, new Set());
    }
    this.callbacks.get(channel)!.add(callback);
    
    return () => {
      const channelCbs = this.callbacks.get(channel);
      if (channelCbs) {
        channelCbs.delete(callback);
      }
    };
  }

  send(channel: string, data: any) {
    const ws = this.sockets.get(channel);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }

  private startHeartbeat(channel: string, ws: WebSocket) {
    const interval = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
    this.pingIntervals.set(channel, interval);
  }

  private stopHeartbeat(channel: string) {
    const interval = this.pingIntervals.get(channel);
    if (interval) {
      clearInterval(interval);
      this.pingIntervals.delete(channel);
    }
  }
}

export const wsService = new WebSocketService();
