// حافظه‌ی وضعیت برنامه — فقط در متغیرهای جاوااسکریپت (RAM) نگه‌داری می‌شود.
// یعنی با رفرش کردن صفحه، لاگین ادمین از دست می‌رود و باید دوباره لاگین کنید.

const listeners = new Set();

export const state = {
  adminToken: null,
  adminUsername: null,
};

export function setState(patch) {
  Object.assign(state, patch);
  listeners.forEach((fn) => fn());
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function logoutAdmin() {
  setState({ adminToken: null, adminUsername: null });
}
