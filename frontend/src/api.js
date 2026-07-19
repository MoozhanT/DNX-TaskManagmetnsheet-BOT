// تمام درخواست‌های fetch به بک‌اند از همین فایل رد می‌شوند
import { API_BASE_URL } from './config.js';

async function request(path, { method = 'GET', body, token, params } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const query = params
    ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))
    : '';

  const res = await fetch(`${API_BASE_URL}${path}${query}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try {
    data = await res.json();
  } catch {
    // بدنه‌ی پاسخ خالی بود (مثلاً حذف‌ها)
  }

  if (!res.ok) {
    const message = (data && data.detail) || `خطای ${res.status}`;
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  // احراز هویت پنل وب
  adminSetup: (payload) => request('/api/admin/setup', { method: 'POST', body: payload }),
  adminLogin: (payload) => request('/api/admin/login', { method: 'POST', body: payload }),

  // تسک‌ها
  getTasks: (token, filters) => request('/api/tasks', { token, params: filters }),
  createTask: (payload, token) => request('/api/tasks', { method: 'POST', body: payload, token }),
  updateTask: (id, payload, token) => request(`/api/tasks/${id}`, { method: 'PATCH', body: payload, token }),
  deleteTask: (id, token) => request(`/api/tasks/${id}`, { method: 'DELETE', token }),

  // اعضای تیم
  getMembers: (token) => request('/api/members', { token }),
  updateMember: (id, payload, token) => request(`/api/members/${id}`, { method: 'PATCH', body: payload, token }),
};

export { API_BASE_URL };
