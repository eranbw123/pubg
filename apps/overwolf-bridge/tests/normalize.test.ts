import { describe, expect, it } from 'vitest';

import { normalize, parseMaybeNestedJson } from '../src/normalize.js';

describe('parseMaybeNestedJson', () => {
  it('decodes the nested JSON string Overwolf actually sends', () => {
    expect(parseMaybeNestedJson('{"x":2300,"y":5740,"z":1520}')).toEqual({
      x: 2300,
      y: 5740,
      z: 1520,
    });
  });

  it('decodes repeated wrapping', () => {
    const doubly = JSON.stringify(JSON.stringify({ x: 1, y: 2, z: 3 }));
    expect(parseMaybeNestedJson(doubly)).toEqual({ x: 1, y: 2, z: 3 });
  });

  it('leaves a plain string alone', () => {
    expect(parseMaybeNestedJson('Erangel_Main')).toBe('Erangel_Main');
  });

  it('returns malformed JSON unchanged rather than inventing a value', () => {
    const broken = '{"x":1,"y":';
    expect(parseMaybeNestedJson(broken)).toBe(broken);
  });

  it('respects the depth limit', () => {
    const deep = JSON.stringify(JSON.stringify(JSON.stringify({ a: 1 })));
    expect(typeof parseMaybeNestedJson(deep, 1)).toBe('string');
    expect(parseMaybeNestedJson(deep, 3)).toEqual({ a: 1 });
  });
});

describe('normalize', () => {
  it('extracts position from the documented location payload', () => {
    const result = normalize({
      info: { location: { location: '{"x":2300,"y":5740,"z":1520}' } },
      feature: 'location',
    });
    expect([result.x, result.y, result.z]).toEqual([2300, 5740, 1520]);
    expect(result.warnings).toEqual([]);
  });

  it('handles the getInfo payload shape as well as onInfoUpdates2', () => {
    const result = normalize({ res: { map: { map: 'Erangel_Main' } } });
    expect(result.map).toBe('Erangel_Main');
  });

  it('extracts the me fields the controller gates on', () => {
    const result = normalize({
      info: {
        me: {
          view: 'FPP',
          stance: 'stand',
          movement: 'normal',
          freeView: false,
          inVehicle: false,
        },
      },
    });
    expect(result.view).toBe('FPP');
    expect(result.stance).toBe('stand');
    expect(result.movement).toBe('normal');
    expect(result.freeView).toBe(false);
    expect(result.inVehicle).toBe(false);
  });

  it('warns instead of guessing when location is malformed', () => {
    const result = normalize({ info: { location: { location: '{"x":"nope"}' } } });
    expect(result.x).toBeUndefined();
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  it('reports nothing for an empty payload rather than defaults', () => {
    const result = normalize({});
    expect(result.x).toBeUndefined();
    expect(result.map).toBeUndefined();
    expect(result.phase).toBeUndefined();
    expect(result.warnings).toEqual([]);
  });

  it('coerces string booleans that some providers send', () => {
    const result = normalize({ info: { me: { freeView: 'true' } } });
    expect(result.freeView).toBe(true);
  });
});
