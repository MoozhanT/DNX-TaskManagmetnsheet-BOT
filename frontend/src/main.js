import './style.css';
import { state, subscribe } from './state.js';
import { renderTopbar } from './views/topbar.js';
import { renderLogin } from './views/login.js';
import { renderTasks } from './views/tasks.js';
import { renderMembers } from './views/members.js';

const app = document.querySelector('#app');

function router() {
  const hash = location.hash.replace('#', '') || '/';
  app.innerHTML = '';

  const topbarRoot = document.createElement('div');
  app.appendChild(topbarRoot);
  renderTopbar(topbarRoot);

  const page = document.createElement('div');
  page.className = 'page';
  app.appendChild(page);

  if (hash === '/login') {
    renderLogin(page);
  } else if (!state.adminToken) {
    // بدون ورود، فقط صفحه‌ی لاگین قابل‌دیدن است
    location.hash = '#/login';
  } else if (hash === '/members') {
    renderMembers(page);
  } else {
    renderTasks(page);
  }
}

window.addEventListener('hashchange', router);
subscribe(router); // با ورود/خروج، کل صفحه دوباره رندر می‌شود
router();
