const API_BASE = '';

const api = {
  async request(path, options = {}) {
    const token = localStorage.getItem('token');
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (resp.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login.html';
      throw new Error('Unauthorized');
    }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.detail || resp.statusText);
    }
    return resp.json();
  },

  get(path) { return this.request(path); },
  post(path, body) { return this.request(path, { method: 'POST', body: JSON.stringify(body) }); },
  put(path, body) { return this.request(path, { method: 'PUT', body: JSON.stringify(body) }); },
};

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 2 : 0) + ' ' + units[i];
}

function formatNumber(n) {
  if (n === undefined || n === null) return '0';
  return n.toLocaleString();
}

function formatDate(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('zh-CN');
}

function checkAuth() {
  const token = localStorage.getItem('token');
  if (!token && !window.location.pathname.endsWith('login.html')) {
    window.location.href = '/login.html';
  }
}

async function loadNav(active) {
  const items = [
    { href: '/', label: '仪表盘', id: 'dashboard' },
    { href: '/services.html', label: '服务列表', id: 'services' },
    { href: '/summary.html', label: '每日汇总', id: 'summary' },
    { href: '/alerts.html', label: '告警记录', id: 'alerts' },
    { href: '/settings.html', label: '系统设置', id: 'settings' },
  ];
  const nav = document.getElementById('nav');
  nav.innerHTML = items.map(it =>
    `<a href="${it.href}" class="nav-link ${it.id === active ? 'active' : ''}">${it.label}</a>`
  ).join('') + '<a href="#" class="nav-link" onclick="logout()">退出</a>';
}

function logout() {
  localStorage.removeItem('token');
  window.location.href = '/login.html';
}
