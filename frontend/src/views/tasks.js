// صفحه‌ی اصلی پنل: لیست تسک‌ها، فیلتر بر اساس وضعیت/مسئول، ساخت/ویرایش/حذف/تکمیل
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

function formatDate(iso) {
  if (!iso) return 'بدون موعد';
  const d = new Date(iso);
  return d.toLocaleString('fa-IR', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function toDatetimeLocalValue(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function renderTasks(container) {
  let tasks = [];
  let members = [];
  let filters = { status: '', assignee_id: '' };
  let loading = true;
  let errorMsg = '';

  async function load() {
    loading = true;
    errorMsg = '';
    draw();
    try {
      const [taskList, memberList] = await Promise.all([
        api.getTasks(state.adminToken, filters),
        api.getMembers(state.adminToken),
      ]);
      tasks = taskList;
      members = memberList;
    } catch (err) {
      errorMsg = err.message;
    } finally {
      loading = false;
      draw();
    }
  }

  function memberOptions(selectedId) {
    return (
      `<option value="">— بدون مسئول —</option>` +
      members
        .map((m) => `<option value="${m.id}" ${m.id === selectedId ? 'selected' : ''}>${escapeHtml(m.full_name)}</option>`)
        .join('')
    );
  }

  function taskStatusBadge(task) {
    if (task.status === 'done') return '<span class="badge done">انجام‌شده</span>';
    const overdue = task.due_date && new Date(task.due_date) < new Date();
    return overdue ? '<span class="badge overdue">عقب‌افتاده</span>' : '<span class="badge pending">باز</span>';
  }

  function openTaskModal(task) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <h3>${task ? 'ویرایش تسک' : 'تسک جدید'}</h3>
          <button class="modal-close" id="m-close">&times;</button>
        </div>
        <form class="modal-body" id="task-form">
          <div id="m-msg"></div>
          <div class="field"><label>عنوان</label><input id="m-title" required value="${escapeHtml(task?.title ?? '')}" /></div>
          <div class="field"><label>توضیحات</label><textarea id="m-desc" rows="3">${escapeHtml(task?.description ?? '')}</textarea></div>
          <div class="field"><label>مسئول</label><select id="m-assignee">${memberOptions(task?.assignee?.id ?? '')}</select></div>
          <div class="field"><label>موعد</label><input id="m-due" type="datetime-local" value="${toDatetimeLocalValue(task?.due_date)}" /></div>
          <div class="modal-actions">
            <button class="btn-primary full" type="submit" id="m-submit">${task ? 'ذخیره' : 'ساخت تسک'}</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector('#m-close').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });

    overlay.querySelector('#task-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const msg = overlay.querySelector('#m-msg');
      const submitBtn = overlay.querySelector('#m-submit');
      const title = overlay.querySelector('#m-title').value.trim();
      const description = overlay.querySelector('#m-desc').value.trim();
      const assignee_id = overlay.querySelector('#m-assignee').value || null;
      const dueRaw = overlay.querySelector('#m-due').value;
      const due_date = dueRaw ? new Date(dueRaw).toISOString() : null;

      if (!title) return;
      msg.innerHTML = '';
      submitBtn.disabled = true;
      try {
        if (task) {
          await api.updateTask(task.id, { title, description, assignee_id, due_date }, state.adminToken);
        } else {
          await api.createTask({ title, description, assignee_id, due_date }, state.adminToken);
        }
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
          <div class="main-title">تسک‌ها</div>
          <button class="btn-primary" id="new-task-btn">+ تسک جدید</button>
        </div>
        <div class="filters">
          <select id="filter-status">
            <option value="">همه‌ی وضعیت‌ها</option>
            <option value="pending" ${filters.status === 'pending' ? 'selected' : ''}>باز</option>
            <option value="done" ${filters.status === 'done' ? 'selected' : ''}>انجام‌شده</option>
          </select>
          <select id="filter-assignee">
            <option value="">همه‌ی اعضا</option>
            ${members.map((m) => `<option value="${m.id}" ${filters.assignee_id === m.id ? 'selected' : ''}>${escapeHtml(m.full_name)}</option>`).join('')}
          </select>
        </div>
        ${loading ? '<div class="state-msg">در حال بارگذاری…</div>' : ''}
        ${errorMsg ? `<div class="state-msg error">${escapeHtml(errorMsg)}</div>` : ''}
        ${
          !loading && !errorMsg
            ? tasks.length === 0
              ? '<div class="state-msg">هنوز تسکی ثبت نشده.</div>'
              : `
          <table class="task-table">
            <thead>
              <tr><th>تسک</th><th>مسئول</th><th>موعد</th><th>وضعیت</th><th></th></tr>
            </thead>
            <tbody>
              ${tasks
                .map(
                  (t) => `
                <tr data-id="${t.id}">
                  <td>
                    <div class="task-title">${escapeHtml(t.title)}</div>
                    ${t.description ? `<div class="task-desc">${escapeHtml(t.description)}</div>` : ''}
                  </td>
                  <td>${t.assignee ? escapeHtml(t.assignee.full_name) : '—'}</td>
                  <td>${formatDate(t.due_date)}</td>
                  <td>${taskStatusBadge(t)}</td>
                  <td>
                    <div class="row-actions">
                      <button class="btn-secondary edit-btn" data-id="${t.id}">ویرایش</button>
                      ${t.status !== 'done' ? `<button class="btn-done done-btn" data-id="${t.id}">تکمیل</button>` : ''}
                      <button class="btn-danger delete-btn" data-id="${t.id}">حذف</button>
                    </div>
                  </td>
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

    const newBtn = container.querySelector('#new-task-btn');
    if (newBtn) newBtn.addEventListener('click', () => openTaskModal(null));

    const statusFilter = container.querySelector('#filter-status');
    if (statusFilter) {
      statusFilter.addEventListener('change', () => {
        filters.status = statusFilter.value;
        load();
      });
    }

    const assigneeFilter = container.querySelector('#filter-assignee');
    if (assigneeFilter) {
      assigneeFilter.addEventListener('change', () => {
        filters.assignee_id = assigneeFilter.value;
        load();
      });
    }

    container.querySelectorAll('.edit-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const task = tasks.find((t) => t.id === btn.dataset.id);
        if (task) openTaskModal(task);
      });
    });

    container.querySelectorAll('.done-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        try {
          await api.updateTask(btn.dataset.id, { status: 'done' }, state.adminToken);
          load();
        } catch (err) {
          errorMsg = err.message;
          draw();
        }
      });
    });

    container.querySelectorAll('.delete-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!confirm('این تسک برای همیشه حذف شود؟')) return;
        btn.disabled = true;
        try {
          await api.deleteTask(btn.dataset.id, state.adminToken);
          load();
        } catch (err) {
          errorMsg = err.message;
          draw();
        }
      });
    });
  }

  load();
}
