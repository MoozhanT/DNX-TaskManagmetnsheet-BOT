// لیست اعضای تیم که با /start در بات تلگرام ثبت شده‌اند + امکان ویرایش نام و دسترسی مدیریتی بات
import { api } from '../api.js';
import { state } from '../state.js';

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c]);
}

export function renderMembers(container) {
  let members = [];
  let loading = true;
  let errorMsg = '';

  async function load() {
    loading = true;
    errorMsg = '';
    draw();
    try {
      members = await api.getMembers(state.adminToken);
    } catch (err) {
      errorMsg = err.message;
    } finally {
      loading = false;
      draw();
    }
  }

  function openEditModal(member) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <h3>ویرایش عضو</h3>
          <button class="modal-close" id="m-close">&times;</button>
        </div>
        <form class="modal-body" id="member-form">
          <div id="m-msg"></div>
          <div class="field"><label>نام کامل</label><input id="m-name" required value="${escapeHtml(member.full_name)}" /></div>
          <div class="field">
            <label><input type="checkbox" id="m-admin" ${member.is_admin_bot ? 'checked' : ''} /> دسترسی مدیریتی بات</label>
          </div>
          <div class="modal-actions">
            <button class="btn-primary full" type="submit" id="m-submit">ذخیره</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector('#m-close').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });

    overlay.querySelector('#member-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const msg = overlay.querySelector('#m-msg');
      const submitBtn = overlay.querySelector('#m-submit');
      const full_name = overlay.querySelector('#m-name').value.trim();
      const is_admin_bot = overlay.querySelector('#m-admin').checked;
      if (!full_name) return;
      msg.innerHTML = '';
      submitBtn.disabled = true;
      try {
        await api.updateMember(member.id, { full_name, is_admin_bot }, state.adminToken);
        overlay.remove();
        load();
      } catch (err) {
        msg.innerHTML = `<div class="error-text">${escapeHtml(err.message)}</div>`;
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  function draw() {
    container.innerHTML = `
      <div class="main">
        <div class="main-head">
          <div class="main-title">اعضای تیم</div>
        </div>
        <div class="state-msg">
          اعضا با فرستادن دستور <code>/start</code> به بات تلگرام، خودکار به این لیست اضافه می‌شوند.
        </div>
        ${loading ? '<div class="state-msg">در حال بارگذاری…</div>' : ''}
        ${errorMsg ? `<div class="state-msg error">${escapeHtml(errorMsg)}</div>` : ''}
        ${
          !loading && !errorMsg
            ? members.length === 0
              ? '<div class="state-msg">هنوز عضوی ثبت نشده.</div>'
              : `
          <table class="task-table">
            <thead>
              <tr><th>نام</th><th>یوزرنیم تلگرام</th><th>دسترسی مدیریتی بات</th><th></th></tr>
            </thead>
            <tbody>
              ${members
                .map(
                  (m) => `
                <tr>
                  <td class="task-title">${escapeHtml(m.full_name)}</td>
                  <td>${m.telegram_username ? '@' + escapeHtml(m.telegram_username) : '—'}</td>
                  <td>${m.is_admin_bot ? '<span class="badge done">دارد</span>' : '—'}</td>
                  <td><button class="btn-secondary edit-btn" data-id="${m.id}">ویرایش</button></td>
                </tr>
              `,
                )
                .join('')}
            </tbody>
          </table>
        `
            : ''
        }
      </div>
    `;

    container.querySelectorAll('.edit-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const member = members.find((m) => m.id === btn.dataset.id);
        if (member) openEditModal(member);
      });
    });
  }

  load();
}
