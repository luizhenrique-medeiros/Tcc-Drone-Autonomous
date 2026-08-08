export const formatCurrency = (value: string | number) =>
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(Number(value));

export const formatDateTime = (value?: string | null) => {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--';
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
};

export const formatTime = (value?: string | null) => {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--';
  return new Intl.DateTimeFormat('pt-BR', { timeStyle: 'medium' }).format(date);
};

export const formatCoordinate = (value: number) => value.toFixed(6);

export const formatOptionalNumber = (
  value: number | null | undefined,
  options?: Intl.NumberFormatOptions,
) =>
  value === null || value === undefined || !Number.isFinite(value)
    ? '--'
    : value.toLocaleString('pt-BR', options);

export const formatPercent = (value: number | null | undefined) => {
  const formatted = formatOptionalNumber(value, { maximumFractionDigits: 0 });
  return formatted === '--' ? formatted : `${formatted}%`;
};

export const formatNullableText = (value: string | null | undefined) =>
  value?.trim() ? value : '--';

export const shortId = (id: string) => id.slice(0, 8).toUpperCase();

export const formatDistance = (meters?: number) => {
  if (meters === undefined) return 'Não calculada';
  return meters >= 1000
    ? `${(meters / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} km`
    : `${Math.round(meters)} m`;
};
