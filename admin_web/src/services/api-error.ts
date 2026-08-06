export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly fields?: Record<string, string | string[]>;

  constructor(
    message: string,
    status = 0,
    code?: string,
    fields?: Record<string, string | string[]>,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

export const getErrorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : 'Não foi possível concluir a operação. Tente novamente.';
