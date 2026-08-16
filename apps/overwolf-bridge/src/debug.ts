/**
 * Debug window: shows what the bridge is doing and lets the operator paste the
 * session token. Read-only with respect to the game.
 */

interface BridgeApi {
  status: () => {
    connected: boolean;
    authenticated: boolean;
    sent: number;
    queued: number;
    reconnects: number;
    lastError: string;
  } | null;
  sessionId: string;
  setToken: (value: string) => void;
  getToken: () => string;
  setPort: (value: number) => void;
  getPort: () => number;
  reconnect: () => void;
}

function text(id: string, value: string, cls?: string): void {
  const element = document.getElementById(id);
  if (!element) return;
  element.textContent = value;
  if (cls) element.className = cls;
}

function append(id: string, line: string, limit = 60): void {
  const element = document.getElementById(id);
  if (!element) return;
  const lines = element.textContent ? element.textContent.split('\n') : [];
  lines.push(line);
  element.textContent = lines.slice(-limit).join('\n');
  element.scrollTop = element.scrollHeight;
}

// getMainWindow is synchronous: it returns the background page's window object.
const mainWindow = overwolf.windows.getMainWindow() as unknown as Window;

function attach(): void {
  const api = (mainWindow as unknown as Record<string, unknown>)['pubgBridge'] as
    | BridgeApi
    | undefined;

  const tokenInput = document.getElementById('token') as HTMLInputElement | null;
  const portInput = document.getElementById('port') as HTMLInputElement | null;

  if (api && tokenInput && portInput) {
    tokenInput.value = api.getToken();
    portInput.value = String(api.getPort());
  }

  document.getElementById('apply')?.addEventListener('click', () => {
    if (!api || !tokenInput || !portInput) return;
    api.setToken(tokenInput.value.trim());
    api.setPort(Number(portInput.value));
    api.reconnect();
    append('log', `saved token and port ${portInput.value}; reconnecting`);
  });

  mainWindow.addEventListener('bridge-log', (event) => {
    append('log', String((event as CustomEvent).detail));
  });

  mainWindow.addEventListener('bridge-payload', (event) => {
    const detail = (event as CustomEvent).detail as { type: string; raw: unknown };
    const element = document.getElementById('payload');
    if (element) {
      element.textContent = `${detail.type}\n${JSON.stringify(detail.raw, null, 2)}`.slice(0, 4000);
    }
  });

  setInterval(() => {
    const status = api?.status();
    if (!status) {
      text('connected', 'no transport', 'bad');
      return;
    }
    text('connected', String(status.connected), status.connected ? 'ok' : 'bad');
    text('authenticated', String(status.authenticated), status.authenticated ? 'ok' : 'bad');
    text('sent', String(status.sent));
    text('queued', String(status.queued));
    text('reconnects', String(status.reconnects));
    text('lastError', status.lastError || 'none', status.lastError ? 'bad' : 'ok');
  }, 500);
}

attach();
