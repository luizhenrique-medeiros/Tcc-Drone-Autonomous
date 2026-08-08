import { appConfig } from './config';
import { demoApi } from './demo-api';
import { realApi } from './real-api';

export const adminApi = appConfig.demoMode ? demoApi : realApi;

export * from './api-error';
export * from './config';
export * from './operational-alerts';
export type * from './contracts';
