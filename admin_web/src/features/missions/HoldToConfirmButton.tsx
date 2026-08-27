import { Power } from 'lucide-react';
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
} from 'react';
import { Button } from '../../design-system/components';

interface HoldToConfirmButtonProps {
  disabled?: boolean;
  loading?: boolean;
  durationMs?: number;
  onConfirm: () => void | Promise<void>;
}

export function HoldToConfirmButton({
  disabled = false,
  loading = false,
  durationMs = 2_000,
  onConfirm,
}: HoldToConfirmButtonProps) {
  const [holding, setHolding] = useState(false);
  const timerRef = useRef<number | null>(null);
  const statusId = useId();

  const cancelHold = useCallback(() => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = null;
    setHolding(false);
  }, []);

  const startHold = useCallback(() => {
    if (disabled || loading || timerRef.current !== null) return;
    setHolding(true);
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      setHolding(false);
      void onConfirm();
    }, durationMs);
  }, [disabled, durationMs, loading, onConfirm]);

  useEffect(() => cancelHold, [cancelHold]);
  useEffect(() => {
    if (disabled || loading) cancelHold();
  }, [cancelHold, disabled, loading]);

  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    startHold();
  };
  const onPointerEnd = (event: PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    cancelHold();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if ((event.key === ' ' || event.key === 'Enter') && !event.repeat) {
      event.preventDefault();
      startHold();
    }
  };
  const onKeyUp = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === ' ' || event.key === 'Enter') {
      event.preventDefault();
      cancelHold();
    }
  };

  return (
    <div
      className="hold-confirm"
      style={{ '--hold-duration': `${durationMs}ms` } as CSSProperties}
    >
      <Button
        type="button"
        variant="warning"
        className={`hold-confirm__button ${holding ? 'hold-confirm__button--active' : ''}`}
        disabled={disabled}
        loading={loading}
        aria-describedby={statusId}
        onClick={(event) => event.preventDefault()}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
        onPointerLeave={onPointerEnd}
        onKeyDown={onKeyDown}
        onKeyUp={onKeyUp}
        onContextMenu={(event) => event.preventDefault()}
      >
        <Power size={18} /> Segure para solicitar armamento
      </Button>
      <small id={statusId} className="hold-confirm__status" aria-live="polite">
        {holding
          ? 'Continue segurando até completar 2 segundos.'
          : 'Mantenha o botão pressionado por 2 segundos. Soltar cancela.'}
      </small>
    </div>
  );
}
