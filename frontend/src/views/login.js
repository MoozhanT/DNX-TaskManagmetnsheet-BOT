// صفحه‌ی ورود ادمین + راه‌اندازی اولین حساب (setup، فقط یک‌بار قابل انجام است)
import { api } from '../api.js';
import { setState } from '../state.js';

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c]);
}

export function renderLogin(container) {
  let mode = 'login';

  function render() {
    container.innerHTML =
      mode === 'login'
        ? `
      <div class="auth-page">
        <div class="auth-card">
          <div class="auth-title">ورود به پنل مدیریت</div>
          <div class="auth-sub">با نام کاربری و رمزی که ساخته‌ای وارد شو</div>
          <div id="auth-msg"></div>
          <form class="auth-form" id="login-form">
            <div class="field"><label>نام کاربری</label><input id="f-username" required /></div>
            <div class="field"><label>رمز عبور</label><input id="f-password" type="password" required /></div>
            <button class="btn-primary full" type="submit" id="f-submit">ورود</button>
          </form>
          <div class="auth-switch">
            <button id="to-setup-btn">هنوز حساب نساخته‌ام — راه‌اندازی اولین حساب</button>
          </div>
        </div>
      </div>
    `
        : `
      <div class="auth-page">
        <div class="auth-card">
          <div class="auth-title">راه‌اندازی اولین حساب ادمین</div>
          <div class="auth-sub">این کار فقط یک‌بار قابل انجام است؛ بعد از آن باید از همین صفحه با «ورود» وارد شوی</div>
          <div id="auth-msg"></div>
          <form class="auth-form" id="setup-form">
            <div class="field"><label>نام کاربری</label><input id="s-username" required /></div>
            <div class="field"><label>رمز عبور</label><input id="s-password" type="password" required minlength="4" /></div>
            <button class="btn-primary full" type="submit" id="s-submit">ساخت حساب</button>
          </form>
          <div class="auth-switch">
            <button id="to-login-btn">بازگشت به ورود</button>
          </div>
        </div>
      </div>
    `;

    if (mode === 'login') {
      const form = container.querySelector('#login-form');
      const msg = container.querySelector('#auth-msg');
      const submitBtn = container.querySelector('#f-submit');

      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = container.querySelector('#f-username').value.trim();
        const password = container.querySelector('#f-password').value;
        if (!username || !password) return;
        msg.innerHTML = '';
        submitBtn.disabled = true;
        try {
          const res = await api.adminLogin({ username, password });
          setState({ adminToken: res.access_token, adminUsername: username });
          location.hash = '#/';
        } catch (err) {
          msg.innerHTML = `<div class="error-text">${escapeHtml(err.message)}</div>`;
        } finally {
          submitBtn.disabled = false;
        }
      });

      container.querySelector('#to-setup-btn').addEventListener('click', () => {
        mode = 'setup';
        render();
      });
    } else {
      const form = container.querySelector('#setup-form');
      const msg = container.querySelector('#auth-msg');
      const submitBtn = container.querySelector('#s-submit');

      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = container.querySelector('#s-username').value.trim();
        const password = container.querySelector('#s-password').value;
        if (!username || !password) return;
        msg.innerHTML = '';
        submitBtn.disabled = true;
        try {
          const res = await api.adminSetup({ username, password });
          setState({ adminToken: res.access_token, adminUsername: username });
          location.hash = '#/';
        } catch (err) {
          msg.innerHTML = `<div class="error-text">${escapeHtml(err.message)}</div>`;
        } finally {
          submitBtn.disabled = false;
        }
      });

      container.querySelector('#to-login-btn').addEventListener('click', () => {
        mode = 'login';
        render();
      });
    }
  }

  render();
}
