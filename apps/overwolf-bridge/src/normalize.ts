/**
 * Advisory normalisation of Overwolf PUBG payloads.
 *
 * The controller re-derives everything from the raw payload itself, so this
 * exists for the debug window and for cross-checking - never as the
 * controller's source of truth. That is why it is a pure function of its input
 * with no Overwolf globals: it is unit-tested directly.
 *
 * The one shape that genuinely matters: `location` arrives as a JSON *string*,
 * e.g. `{"location": "{\"x\":2300,\"y\":5740,\"z\":1520}"}`.
 */

export interface NormalizedView {
  x?: number;
  y?: number;
  z?: number;
  map?: string;
  phase?: string;
  view?: string;
  stance?: string;
  movement?: string;
  freeView?: boolean;
  inVehicle?: boolean;
  warnings: string[];
}

/** Decode a value that may be JSON wrapped in a string, possibly repeatedly. */
export function parseMaybeNestedJson(value: unknown, maxDepth = 3): unknown {
  let current = value;
  for (let i = 0; i < maxDepth; i += 1) {
    if (typeof current !== 'string') break;
    const trimmed = current.trim();
    if (trimmed.length === 0) break;
    const first = trimmed[0];
    if (first !== '{' && first !== '[' && first !== '"') break;
    try {
      current = JSON.parse(trimmed) as unknown;
    } catch {
      // Malformed: hand back what we were given rather than inventing a value.
      return current;
    }
  }
  return current;
}

function sections(raw: Record<string, unknown>): Record<string, Record<string, unknown>> {
  for (const key of ['info', 'res']) {
    const value = raw[key];
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return value as Record<string, Record<string, unknown>>;
    }
  }
  return raw as Record<string, Record<string, unknown>>;
}

export function normalize(raw: Record<string, unknown>): NormalizedView {
  const result: NormalizedView = { warnings: [] };
  const info = sections(raw);

  const location = info['location'];
  if (location && typeof location === 'object' && 'location' in location) {
    const decoded = parseMaybeNestedJson((location as Record<string, unknown>)['location']);
    if (decoded && typeof decoded === 'object') {
      const point = decoded as Record<string, unknown>;
      const x = Number(point['x']);
      const y = Number(point['y']);
      const z = Number(point['z']);
      if ([x, y, z].every((n) => Number.isFinite(n))) {
        result.x = x;
        result.y = y;
        result.z = z;
      } else {
        result.warnings.push(`location has non-numeric components: ${JSON.stringify(point)}`);
      }
    } else {
      result.warnings.push('location did not decode to an object');
    }
  }

  const map = info['map'];
  if (map && typeof map === 'object' && typeof map['map'] === 'string') {
    result.map = map['map'] as string;
  }

  const phase = info['phase'];
  if (phase && typeof phase === 'object' && phase['phase'] !== undefined) {
    result.phase = String(phase['phase']);
  }

  const me = info['me'];
  if (me && typeof me === 'object') {
    const record = me as Record<string, unknown>;
    if (record['view'] !== undefined) result.view = String(record['view']);
    if (record['stance'] !== undefined) result.stance = String(record['stance']);
    if (record['movement'] !== undefined) result.movement = String(record['movement']);
    if (record['freeView'] !== undefined) result.freeView = record['freeView'] === true
      || record['freeView'] === 'true';
    if (record['inVehicle'] !== undefined) result.inVehicle = record['inVehicle'] === true
      || record['inVehicle'] === 'true';
  }

  return result;
}
