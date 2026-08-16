/**
 * Wire contract shared with the Python controller.
 *
 * Must stay in step with `schemas/bridge-message.schema.json` and
 * `src/pubg_training_bot/protocol/envelope.py`. `PROTOCOL_VERSION` is checked
 * on both sides at auth time, so a mismatch fails loudly at connect rather
 * than as mysterious missing data later.
 */

export const PROTOCOL_VERSION = 1;

/** PUBG class ID, from Overwolf's games list (instance 109061 / 10 = 10906). */
export const PUBG_CLASS_ID = 10906;

/**
 * Documented features we register. Deliberately narrow: combat and roster
 * features are not requested at all, so out-of-scope data never reaches this
 * process in the first place.
 */
export const REQUIRED_FEATURES = [
  'location',
  'me',
  'phase',
  'map',
  'match_info',
] as const;

export type FrameType =
  | 'hello'
  | 'heartbeat'
  | 'feature_status'
  | 'info_update'
  | 'game_event'
  | 'game_info'
  | 'bridge_error';

export interface AuthRequest {
  type: 'auth';
  protocol_version: number;
  token: string;
  bridge_version: string;
  session_id: string;
  overwolf_version: string;
}

export interface AuthResponse {
  type: string;
  accepted: boolean;
  detail: string;
  heartbeat_interval_s: number;
}

export interface BridgeFrame {
  type: FrameType;
  sequence: number;
  /** Milliseconds since bridge start (monotonic-ish). */
  bridge_ts_ms: number;
  /** Wall-clock epoch milliseconds, when available. */
  source_ts_ms: number | null;
  /** Untouched payload exactly as Overwolf delivered it. */
  raw: Record<string, unknown>;
  /** Advisory only; the controller re-derives its own view from `raw`. */
  normalized: Record<string, unknown> | null;
  feature: string | null;
}

export interface FeatureRegistration {
  feature: string;
  registered: boolean;
  detail: string;
}
