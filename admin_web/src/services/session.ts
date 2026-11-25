const TOKEN_KEY = 'devcore.admin.token';
const BENCH_MODE_KEY = 'devcore.admin.bench-mode';

export const benchModePreference = {
  get: () => sessionStorage.getItem(BENCH_MODE_KEY) === 'true',
  set: (enabled: boolean) => {
    if (enabled) {
      sessionStorage.setItem(BENCH_MODE_KEY, 'true');
    } else {
      sessionStorage.removeItem(BENCH_MODE_KEY);
    }
  },
};

export const sessionToken = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => {
    sessionStorage.removeItem(TOKEN_KEY);
    benchModePreference.set(false);
  },
};
