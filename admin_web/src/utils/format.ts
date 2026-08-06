export const formatCurrency = (value: string | number) =>
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(Number(value));

export const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
};

export const formatTime = (value?: string) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('pt-BR', { timeStyle: 'medium' }).format(date);
};

export const formatCoordinate = (value: number) => value.toFixed(6);

export const shortId = (id: string) => id.slice(0, 8).toUpperCase();

export const formatDistance = (meters?: number) => {
  if (meters === undefined) return 'Não calculada';
  return meters >= 1000
    ? `${(meters / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} km`
    : `${Math.round(meters)} m`;
};
