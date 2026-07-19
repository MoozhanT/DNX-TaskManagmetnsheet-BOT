// نوار باریک بالای صفحه: لینک‌های ناوبری + ورود/خروج ادمین
import { state, logoutAdmin } from '../state.js';

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c]);
}

export function renderTopbar(container) {
  const adminSection = state.adminToken
    ? `<span class="topbar-hello">سلام ${escapeHtml(state.adminUsername)}</span><button class="link" id="admin-logout">خروج</button>`
    : `<a href="#/login">ورود</a>`;

  const navLinks = state.adminToken
    ? `<a href="#/">تسک‌ها</a><a href="#/members">اعضا</a>`
    : '';

  container.innerHTML = `
    <div class="topbar">
      <div class="topbar-inner">
        <div class="topbar-links">${navLinks}</div>
        <div class="topbar-links">${adminSection}</div>
      </div>
    </div>
  `;

  const logoutBtn = container.querySelector('#admin-logout');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      logoutAdmin();
      location.hash = '#/login';
    });
  }
}
