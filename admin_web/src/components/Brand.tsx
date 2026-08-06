export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? 'brand--compact' : ''}`}>
      <span className="brand__logo-crop">
        <img
          src="/devcore-logo-source.png"
          alt="DevCore — drone de entregas"
          draggable="false"
        />
      </span>
      {!compact ? <span className="brand__descriptor">Centro de operações</span> : null}
    </div>
  );
}
