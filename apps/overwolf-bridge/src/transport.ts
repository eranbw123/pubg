/**
 * Loopback WebSocket client: auth, heartbeat, reconnect, sequence numbering.
 *
 * Frames produced while disconnected are queued to a bounded buffer rather than
 * dropped silently, so a brief controller restart does not punch an unexplained
 * hole in the trace. The buffer is bounded because an unbounded one would turn
 * a disconnected controller into a memory leak inside the game overlay.
 */

import { PROTOCOL_VERSION, type AuthRequest, type BridgeFrame, type FrameType } from './types.js';

export interface TransportOptions {
  url: string;
  token: string;
  sessionId: string;
  bridgeVersion: string;
  overwolfVersion?: string;
  maxQueued?: number;
  reconnectDelayMs?: number;
  onStatus?: (status: TransportStatus) => void;
}

export interface TransportStatus {
  connected: boolean;
  authenticated: boolean;
  sent: number;
  queued: number;
  reconnects: number;
  lastError: string;
}

export class BridgeTransport {
  private socket: WebSocket | null = null;
  private sequence = 0;
  private sent = 0;
  private reconnects = 0;
  private authenticated = false;
  private lastError = '';
  private queue: BridgeFrame[] = [];
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;
  private readonly startedAt = Date.now();

  constructor(private readonly options: TransportOptions) {}

  get status(): TransportStatus {
    return {
      connected: this.socket?.readyState === WebSocket.OPEN,
      authenticated: this.authenticated,
      sent: this.sent,
      queued: this.queue.length,
      reconnects: this.reconnects,
      lastError: this.lastError,
    };
  }

  connect(): void {
    this.closed = false;
    this.open();
  }

  close(): void {
    this.closed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
    this.socket?.close();
    this.socket = null;
    this.authenticated = false;
  }

  private open(): void {
    try {
      this.socket = new WebSocket(this.options.url);
    } catch (error) {
      this.lastError = String(error);
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      const auth: AuthRequest = {
        type: 'auth',
        protocol_version: PROTOCOL_VERSION,
        token: this.options.token,
        bridge_version: this.options.bridgeVersion,
        session_id: this.options.sessionId,
        overwolf_version: this.options.overwolfVersion ?? '',
      };
      this.socket?.send(JSON.stringify(auth));
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const response = JSON.parse(String(event.data)) as { accepted?: boolean; detail?: string };
        if (response.accepted === true) {
          this.authenticated = true;
          this.lastError = '';
          this.flush();
          this.startHeartbeat();
        } else if (response.accepted === false) {
          // A rejected token is a configuration error, not a transient fault:
          // reconnecting in a loop would just spam an unreachable controller.
          this.authenticated = false;
          this.closed = true;
          this.lastError = `auth rejected: ${response.detail ?? 'no detail'}`;
        }
      } catch (error) {
        this.lastError = `bad controller response: ${String(error)}`;
      }
      this.options.onStatus?.(this.status);
    };

    this.socket.onerror = () => {
      this.lastError = 'websocket error';
      this.options.onStatus?.(this.status);
    };

    this.socket.onclose = () => {
      this.authenticated = false;
      this.stopHeartbeat();
      this.options.onStatus?.(this.status);
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (this.closed) return;
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.reconnects += 1;
      this.open();
    }, this.options.reconnectDelayMs ?? 1000);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.send('heartbeat', {}, null, null);
    }, 1000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  send(
    type: FrameType,
    raw: Record<string, unknown>,
    normalized: Record<string, unknown> | null,
    feature: string | null,
  ): void {
    this.sequence += 1;
    const frame: BridgeFrame = {
      type,
      sequence: this.sequence,
      bridge_ts_ms: Date.now() - this.startedAt,
      source_ts_ms: Date.now(),
      raw,
      normalized,
      feature,
    };
    if (this.authenticated && this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(frame));
      this.sent += 1;
    } else {
      this.queue.push(frame);
      const max = this.options.maxQueued ?? 5000;
      if (this.queue.length > max) this.queue.splice(0, this.queue.length - max);
    }
  }

  private flush(): void {
    if (!this.authenticated || this.socket?.readyState !== WebSocket.OPEN) return;
    const pending = this.queue;
    this.queue = [];
    for (const frame of pending) {
      this.socket.send(JSON.stringify(frame));
      this.sent += 1;
    }
  }
}
