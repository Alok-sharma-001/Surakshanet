import React from 'react';

export type TelemetrySource =
  | 'sumo'
  | 'vision'
  | 'mqtt'
  | 'model'
  | 'heuristic'
  | 'manual'
  | 'live'
  | 'sim'
  | 'mock';

interface Props {
  source?: TelemetrySource | string | null;
  className?: string;
  showIcon?: boolean;
}

export const TelemetrySourceBadge: React.FC<Props> = ({
  source = 'mqtt',
  className = '',
  showIcon = true,
}) => {
  if (!source) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold uppercase tracking-wider border bg-slate-50 text-slate-500 border-slate-200 ${className}`}
        title="Telemetry Origin: Unavailable"
      >
        {showIcon && <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />}
        UNAVAILABLE
      </span>
    );
  }

  const normSource = source.toLowerCase();

  const config: Record<
    string,
    {
      label: string;
      bgColor: string;
      textColor: string;
      borderColor: string;
      dotColor: string;
      prefix?: string;
    }
  > = {
    // Measured family (sumo, vision, mqtt)
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
    // Model family
    model: {
      label: 'AI MODEL',
      bgColor: 'bg-purple-50',
      textColor: 'text-purple-700',
      borderColor: 'border-purple-200',
      dotColor: 'bg-purple-500',
    },
    // Heuristic family (distinct amber + "est." prefix)
    heuristic: {
      label: 'HEURISTIC',
      prefix: 'est.',
      bgColor: 'bg-amber-50',
      textColor: 'text-amber-700',
      borderColor: 'border-amber-200',
      dotColor: 'bg-amber-500',
    },
    // Manual
    manual: {
      label: 'MANUAL',
      bgColor: 'bg-slate-100',
      textColor: 'text-slate-700',
      borderColor: 'border-slate-300',
      dotColor: 'bg-slate-500',
    },
    // Legacy aliases
    live: {
      label: 'LIVE (EDGE)',
      bgColor: 'bg-emerald-50',
      textColor: 'text-emerald-700',
      borderColor: 'border-emerald-200',
      dotColor: 'bg-emerald-500',
    },
    sim: {
      label: 'SUMO (SIM)',
      bgColor: 'bg-sky-50',
      textColor: 'text-sky-700',
      borderColor: 'border-sky-200',
      dotColor: 'bg-sky-500',
    },
    mock: {
      label: 'HEURISTIC',
      prefix: 'est.',
      bgColor: 'bg-amber-50',
      textColor: 'text-amber-700',
      borderColor: 'border-amber-200',
      dotColor: 'bg-amber-500',
    },
  };

  const style = config[normSource] || config.mqtt;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold uppercase tracking-wider border ${style.bgColor} ${style.textColor} ${style.borderColor} ${className}`}
      title={`Telemetry Origin: ${style.label}`}
    >
      {showIcon && (
        <span className={`h-1.5 w-1.5 rounded-full ${style.dotColor} animate-pulse`} />
      )}
      {style.prefix && <span className="font-mono text-[10px] lowercase opacity-80">{style.prefix}</span>}
      {style.label}
    </span>
  );
};

export default TelemetrySourceBadge;
