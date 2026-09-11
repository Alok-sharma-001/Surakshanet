import { describe, it } from 'node:test';
import assert from 'node:assert';

// Configuration contract mirroring TelemetrySourceBadge.tsx (SN-009, SN-012b, SN-123)
const BADGE_CONFIG = {
  sumo: {
    label: 'SUMO (SIM)',
    bgColor: 'bg-sky-50',
    textColor: 'text-sky-700',
    borderColor: 'border-sky-200',
    dotColor: 'bg-sky-500',
  },
  vision: {
    label: 'VISION (YOLO)',
    bgColor: 'bg-emerald-50',
    textColor: 'text-emerald-700',
    borderColor: 'border-emerald-200',
    dotColor: 'bg-emerald-500',
  },
  mqtt: {
    label: 'MQTT (EDGE)',
    bgColor: 'bg-teal-50',
    textColor: 'text-teal-700',
    borderColor: 'border-teal-200',
    dotColor: 'bg-teal-500',
  },
  model: {
    label: 'AI MODEL',
    bgColor: 'bg-purple-50',
    textColor: 'text-purple-700',
    borderColor: 'border-purple-200',
    dotColor: 'bg-purple-500',
  },
  heuristic: {
    label: 'HEURISTIC',
    prefix: 'est.',
    bgColor: 'bg-amber-50',
    textColor: 'text-amber-700',
    borderColor: 'border-amber-200',
    dotColor: 'bg-amber-500',
  },
  manual: {
    label: 'MANUAL',
    bgColor: 'bg-slate-100',
    textColor: 'text-slate-700',
    borderColor: 'border-slate-300',
    dotColor: 'bg-slate-500',
  },
};

function resolveBadgeProps(source) {
  if (!source) {
    return {
      label: 'UNAVAILABLE',
      isUnavailable: true,
      prefix: undefined,
      colorFamily: 'slate',
    };
  }
  const norm = source.toLowerCase();
  const cfg = BADGE_CONFIG[norm];
  if (!cfg) {
    // Fail closed (SN-009): unrecognised source renders UNAVAILABLE
    return {
      label: 'UNAVAILABLE',
      isUnavailable: true,
      prefix: undefined,
      colorFamily: 'slate',
    };
  }
  return {
    label: cfg.label,
    isUnavailable: false,
    prefix: cfg.prefix,
    colorFamily: cfg.bgColor.replace('bg-', '').split('-')[0],
  };
}

describe('TelemetrySourceBadge Contract Tests (SN-123)', () => {
  it('heuristic values never render with the model badge', () => {
    const heuristicBadge = resolveBadgeProps('heuristic');
    const modelBadge = resolveBadgeProps('model');

    assert.notStrictEqual(heuristicBadge.label, modelBadge.label);
    assert.strictEqual(heuristicBadge.label, 'HEURISTIC');
    assert.strictEqual(heuristicBadge.prefix, 'est.');
    assert.strictEqual(heuristicBadge.colorFamily, 'amber');

    assert.strictEqual(modelBadge.label, 'AI MODEL');
    assert.strictEqual(modelBadge.prefix, undefined);
    assert.strictEqual(modelBadge.colorFamily, 'purple');
  });

  it('fails closed: absent or unrecognised source renders UNAVAILABLE', () => {
    // Absent sources
    assert.strictEqual(resolveBadgeProps(null).label, 'UNAVAILABLE');
    assert.strictEqual(resolveBadgeProps(undefined).label, 'UNAVAILABLE');
    assert.strictEqual(resolveBadgeProps('').label, 'UNAVAILABLE');

    // Legacy uncanonical sources must NOT be treated as measured
    assert.strictEqual(resolveBadgeProps('mock').label, 'UNAVAILABLE');
    assert.strictEqual(resolveBadgeProps('live').label, 'UNAVAILABLE');
    assert.strictEqual(resolveBadgeProps('sim').label, 'UNAVAILABLE');
    assert.strictEqual(resolveBadgeProps('unknown_src').label, 'UNAVAILABLE');
  });

  it('measured family correctly renders distinct badges for sumo, vision, and mqtt', () => {
    const sumo = resolveBadgeProps('sumo');
    const vision = resolveBadgeProps('vision');
    const mqtt = resolveBadgeProps('mqtt');

    assert.strictEqual(sumo.label, 'SUMO (SIM)');
    assert.strictEqual(sumo.colorFamily, 'sky');

    assert.strictEqual(vision.label, 'VISION (YOLO)');
    assert.strictEqual(vision.colorFamily, 'emerald');

    assert.strictEqual(mqtt.label, 'MQTT (EDGE)');
    assert.strictEqual(mqtt.colorFamily, 'teal');
  });
});
