/**
 * Background page: the whole bridge.
 *
 * Responsibilities: detect PUBG, register the documented features we need,
 * forward every payload verbatim to the controller, and report registration
 * outcomes.
 *
 * It has no input capability of any kind: no Overwolf input or key-simulation
 * API is imported or called anywhere in this app, and the manifest requests
 * only the `GameInfo` permission. `scripts/check-stage-01.ps1` greps this
 * source tree for those APIs and fails the stage if any appear - which is why
 * this comment names none of them.
 */

import { normalize } from './normalize.js';
import { BridgeTransport } from './transport.js';
import { PUBG_CLASS_ID, REQUIRED_FEATURES, type FeatureRegistration } from './types.js';

const BRIDGE_VERSION = '0.1.0';
const TOKEN_STORAGE_KEY = 'pubg-bridge-token';
const PORT_STORAGE_KEY = 'pubg-bridge-port';
const DEFAULT_PORT = 17311;

/** Registration is retried: the provider is not always ready the instant the
 *  game reports as running, and a single failed attempt would leave the bridge
 *  silently receiving nothing. */
const REGISTER_MAX_ATTEMPTS = 12;
const REGISTER_RETRY_MS = 2500;

let transport: BridgeTransport | null = null;
let registered = false;
let attempts = 0;

const sessionId = `ow-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

function token(): string {
  return localStorage.getItem(TOKEN_STORAGE_KEY) ?? '';
}

function port(): number {
  const stored = localStorage.getItem(PORT_STORAGE_KEY);
  const parsed = stored ? Number(stored) : DEFAULT_PORT;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_PORT;
}

function log(message: string): void {
  // eslint-disable-next-line no-console
  console.log(`[pubg-bridge] ${message}`);
  window.dispatchEvent(new CustomEvent('bridge-log', { detail: message }));
}

function startTransport(overwolfVersion: string): void {
  if (transport) return;
  const value = token();
  if (!value) {
    log('no session token set - open the debug window and paste the one the probe printed');
    return;
  }
  transport = new BridgeTransport({
    url: `ws://127.0.0.1:${port()}`,
    token: value,
    sessionId,
    bridgeVersion: BRIDGE_VERSION,
    overwolfVersion,
    onStatus: (status) => {
      window.dispatchEvent(new CustomEvent('bridge-status', { detail: status }));
    },
  });
  transport.connect();
  log(`connecting to ws://127.0.0.1:${port()}`);
}

function forward(
  type: 'info_update' | 'game_event' | 'game_info',
  raw: Record<string, unknown>,
  feature: string | null,
): void {
  let normalized: Record<string, unknown> | null = null;
  try {
    normalized = normalize(raw) as unknown as Record<string, unknown>;
  } catch (error) {
    normalized = { error: String(error) };
  }
  transport?.send(type, raw, normalized, feature);
  window.dispatchEvent(new CustomEvent('bridge-payload', { detail: { type, raw, normalized } }));
}

function registerFeatures(): void {
  if (registered) return;
  attempts += 1;
  overwolf.games.events.setRequiredFeatures([...REQUIRED_FEATURES], (result) => {
    const outcomes: FeatureRegistration[] = [];
    const supported = new Set<string>(
      Array.isArray(result?.supportedFeatures) ? result.supportedFeatures : [],
    );
    for (const feature of REQUIRED_FEATURES) {
      outcomes.push({
        feature,
        // When the provider does not enumerate supported features, success of
        // the call is the only signal available; that ambiguity is recorded in
        // `detail` rather than smoothed over.
        registered: supported.size > 0 ? supported.has(feature) : result.success === true,
        detail:
          supported.size > 0
            ? 'from supportedFeatures'
            : `inferred from setRequiredFeatures success=${String(result.success)}`,
      });
    }

    transport?.send(
      'feature_status',
      {
        features: outcomes,
        attempt: attempts,
        success: result.success,
        error: result.error ?? null,
        raw_result: result as unknown as Record<string, unknown>,
      },
      null,
      null,
    );

    if (result.success) {
      registered = true;
      log(`features registered on attempt ${attempts}`);
      overwolf.games.events.getInfo((info) => {
        forward('game_info', info as unknown as Record<string, unknown>, null);
      });
    } else if (attempts < REGISTER_MAX_ATTEMPTS) {
      log(`feature registration failed (${result.error ?? 'no error'}), retrying`);
      setTimeout(registerFeatures, REGISTER_RETRY_MS);
    } else {
      log(`feature registration gave up after ${attempts} attempts`);
    }
  });
}

function onGameRunning(running: boolean, overwolfVersion: string): void {
  if (!running) {
    registered = false;
    attempts = 0;
    log('PUBG is not running');
    return;
  }
  log('PUBG detected');
  startTransport(overwolfVersion);
  registerFeatures();
}

/**
 * Structural parameter rather than a named Overwolf type: `getRunningGameInfo`
 * and `onGameInfoUpdated` hand back different shapes that both carry the ids.
 *
 * `classId` already equals the manifest game id; `id` is the instance id
 * (109061 for PUBG), so dividing by ten recovers the class id when only `id`
 * is present.
 */
function isPubg(info: { classId?: number; id?: number } | null | undefined): boolean {
  if (!info) return false;
  const classId = info.classId ?? (info.id !== undefined ? Math.floor(info.id / 10) : undefined);
  return classId === PUBG_CLASS_ID;
}

function bootstrap(): void {
  overwolf.games.events.onInfoUpdates2.addListener((update) => {
    forward('info_update', update as unknown as Record<string, unknown>, update.feature ?? null);
  });
  overwolf.games.events.onNewEvents.addListener((events) => {
    forward('game_event', events as unknown as Record<string, unknown>, null);
  });
  overwolf.games.events.onError.addListener((error) => {
    transport?.send('bridge_error', error as unknown as Record<string, unknown>, null, null);
    log(`GEP error: ${JSON.stringify(error)}`);
  });

  overwolf.extensions.current.getManifest((manifest) => {
    const version = manifest?.meta?.version ?? 'unknown';
    log(`bridge ${version} starting (session ${sessionId})`);
    overwolf.games.getRunningGameInfo((info) => {
      onGameRunning(isPubg(info) && info?.isRunning === true, version);
    });
    overwolf.games.onGameInfoUpdated.addListener((update) => {
      if (!isPubg(update.gameInfo)) return;
      onGameRunning(update.gameInfo?.isRunning === true, version);
    });
  });
}

// Expose a minimal surface for the debug window. Read-only by design.
(window as unknown as Record<string, unknown>)['pubgBridge'] = {
  status: () => transport?.status ?? null,
  sessionId,
  setToken: (value: string) => localStorage.setItem(TOKEN_STORAGE_KEY, value),
  getToken: token,
  setPort: (value: number) => localStorage.setItem(PORT_STORAGE_KEY, String(value)),
  getPort: port,
  reconnect: () => {
    transport?.close();
    transport = null;
    overwolf.extensions.current.getManifest((manifest) => {
      startTransport(manifest?.meta?.version ?? 'unknown');
      registered = false;
      attempts = 0;
      registerFeatures();
    });
  },
};

bootstrap();
