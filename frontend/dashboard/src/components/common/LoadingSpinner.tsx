import React from 'react';
import { Loader2 } from 'lucide-react';

export interface LoadingSpinnerProps {
  size?: number;
  className?: string;
  text?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ size = 24, className = '', text }) => {
  return (
    <div className={`flex flex-col justify-center items-center ${className}`}>
      <Loader2 size={size} className="animate-spin text-blue-600 mb-2" />
      {text && <span className="text-sm text-gray-500 font-medium">{text}</span>}
    </div>
  );
};
