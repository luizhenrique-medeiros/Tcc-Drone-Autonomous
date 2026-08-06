import { AlertTriangle, Inbox, LoaderCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button } from './Button';

interface StateViewProps {
  state: 'loading' | 'empty' | 'error';
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  compact?: boolean;
  children?: ReactNode;
}

export function StateView({
  state,
  title,
  description,
  actionLabel,
  onAction,
  compact = false,
  children,
}: StateViewProps) {
  const Icon = state === 'loading' ? LoaderCircle : state === 'error' ? AlertTriangle : Inbox;
  const fallbackTitle =
    state === 'loading'
      ? 'Carregando dados operacionais'
      : state === 'error'
        ? 'Não foi possível carregar'
        : 'Nenhum registro encontrado';

  return (
    <div
      className="state-view"
      style={compact ? { minHeight: '9rem' } : undefined}
      aria-live="polite"
    >
      <div className="state-view__content">
        <span className="state-view__icon">
          <Icon
            size={24}
            className={state === 'loading' ? 'spinner' : undefined}
            aria-hidden="true"
          />
        </span>
        <h2>{title ?? fallbackTitle}</h2>
        {description ? <p className="muted">{description}</p> : null}
        {children}
        {actionLabel && onAction ? (
          <Button variant="secondary" onClick={onAction}>
            {actionLabel}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
