import { AlertCircle, CheckCircle2, Info, TriangleAlert } from 'lucide-react';
import type { ReactNode } from 'react';

interface FeedbackProps {
  tone?: 'info' | 'error' | 'warning' | 'success';
  children: ReactNode;
  className?: string;
}

export function Feedback({
  tone = 'info',
  children,
  className = '',
}: FeedbackProps) {
  const Icon =
    tone === 'error'
      ? AlertCircle
      : tone === 'warning'
        ? TriangleAlert
        : tone === 'success'
          ? CheckCircle2
          : Info;
  return (
    <div
      className={`feedback ${tone !== 'info' ? `feedback--${tone}` : ''} ${className}`.trim()}
      role={tone === 'error' ? 'alert' : 'status'}
    >
      <Icon size={19} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}
