interface SparklineProps {
  values: number[];
  label: string;
  color?: 'blue' | 'orange' | 'green';
}

export function Sparkline({ values, label, color = 'blue' }: SparklineProps) {
  if (values.length < 2) return <div className="sparkline sparkline--empty">Sem série suficiente</div>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 0.01);
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      const y = 34 - ((value - min) / range) * 28;
      return `${x},${y}`;
    })
    .join(' ');
  return (
    <svg
      className={`sparkline sparkline--${color}`}
      viewBox="0 0 100 40"
      preserveAspectRatio="none"
      role="img"
      aria-label={label}
    >
      <polyline points={points} />
    </svg>
  );
}
