import React from 'react';

export type TelemetrySource = 'live' | 'sim' | 'mock';

interface Props {
  source?: TelemetrySource | string;
  className?: string;
  showIcon?: boolean;
}

export const TelemetrySourceBadge: React.FC<Props> = ({
  source = 'live',
  className = '',
  showIcon = true,
}) => {
  const normSource = (source || 'live').toLowerCase() as TelemetrySource;

  const config = {
    live: {
      label: 'LIVE',
      bgColor: 'bg-emerald-50',
      textColor: 'text-emerald-700',
      borderColor: 'border-emerald-200',
      dotColor: 'bg-emerald-500',
    },
    sim: {
      label: 'SIM',
      bgColor: 'bg-sky-50',
      textColor: 'text-sky-700',
      borderColor: 'border-sky-200',
      dotColor: 'bg-sky-500',
    },
    mock: {
      label: 'MOCK',
      bgColor: 'bg-amber-50',
      textColor: 'text-amber-700',
      borderColor: 'border-amber-200',
      dotColor: 'bg-amber-500',
    },
  };

  const style = config[normSource] || config.live;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold uppercase tracking-wider border ${style.bgColor} ${style.textColor} ${style.borderColor} ${className}`}
      title={`Telemetry Origin: ${style.label}`}
    >
      {showIcon && (
        <span className={`h-1.5 w-1.5 rounded-full ${style.dotColor} animate-pulse`} />
      )}
      {style.label}
    </span>
  );
};

export default TelemetrySourceBadge;
