type MessageCallback = (data: unknown) => void;

class WebSocketService {
  private sockets: Map<string, WebSocket> = new Map();
  private callbacks: Map<string, Set<MessageCallback>> = new Map();
  private reconnectTimeouts: Map<string, number> = new Map();
  private reconnectAttempts: Map<string, number> = new Map();
  private pingIntervals: Map<string, number> = new Map();

  private baseDelayMs: number = 1000;
  private maxDelayMs: number = 30000;
  private maxAttempts: number = 20;

  connect(channel: string) {
    if (this.sockets.has(channel)) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const apiUrl = (import.meta as { env?: Record<string, string> }).env?.VITE_API_URL;
    let wsUrl: string;

    if (apiUrl) {
      try {
        const parsed = new URL(apiUrl, window.location.href);
        const apiProtocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${apiProtocol}//${parsed.host}/ws/${channel}`;
      } catch {
        wsUrl = `${protocol}//${window.location.host}/ws/${channel}`;
      }
    } else {
      wsUrl = `${protocol}//${window.location.host}/ws/${channel}`;
    }

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log(`[Surakshanet WS] Connected to channel: ${channel} via ${wsUrl}`);
        this.reconnectAttempts.set(channel, 0);
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
        this.sockets.delete(channel);
        this.stopHeartbeat(channel);

        const attempts = this.reconnectAttempts.get(channel) || 0;
        if (attempts >= this.maxAttempts) {
          console.warn(`[Surakshanet WS] Max reconnect attempts (${this.maxAttempts}) reached for ${channel}`);
          return;
        }

        const expDelay = Math.min(this.maxDelayMs, this.baseDelayMs * Math.pow(1.5, attempts));
        const jitter = Math.random() * 500;
        const delay = Math.round(expDelay + jitter);

        console.log(`[Surakshanet WS] Disconnected: ${channel}. Backoff retry #${attempts + 1} in ${delay}ms...`);
        this.reconnectAttempts.set(channel, attempts + 1);

        const timeoutId = window.setTimeout(() => this.connect(channel), delay);
        this.reconnectTimeouts.set(channel, timeoutId);
      };

      ws.onerror = (err) => {
        console.warn(`[Surakshanet WS] Error on ${channel}:`, err);
      };

      this.sockets.set(channel, ws);
    } catch (err) {
      console.error(`[Surakshanet WS] Failed to initialize WebSocket for ${channel}:`, err);
    }
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
    this.reconnectAttempts.delete(channel);
    this.stopHeartbeat(channel);
  }

  subscribe(channel: string, callback: MessageCallback) {
    if (!this.callbacks.has(channel)) {
      this.callbacks.set(channel, new Set());
    }
    this.callbacks.get(channel)!.add(callback);
    this.connect(channel);

    return () => {
      const channelCallbacks = this.callbacks.get(channel);
      if (channelCallbacks) {
        channelCallbacks.delete(callback);
        if (channelCallbacks.size === 0) {
          this.disconnect(channel);
        }
      }
    };
  }

  onMessage(channel: string, callback: MessageCallback) {
    return this.subscribe(channel, callback);
  }

  send(channel: string, data: unknown) {
    const ws = this.sockets.get(channel);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    } else {
      console.warn(`[Surakshanet WS] Cannot send, socket not open for channel: ${channel}`);
    }
  }

  private startHeartbeat(channel: string, ws: WebSocket) {
    this.stopHeartbeat(channel);
    const interval = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: 'ping' }));
        } catch {
          // ignore heartbeat send errors
        }
      }
    }, 15000);
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
export default wsService;
