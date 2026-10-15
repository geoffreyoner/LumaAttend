// ============================================================
//  LumaAttend — global helpers (apiFetch, toast, nav)
// ============================================================
(function () {
  'use strict';

  window.escapeHtml = function (value) {
    var el = document.createElement('span');
    el.textContent = value == null ? '' : String(value);
    return el.innerHTML;
  };

  window.showToast = function (msg, type) {
    type = type || 'info';
    var c = document.getElementById('toastContainer');
    if (!c) { console.log('[toast]', type, msg); return; }
    var t = document.createElement('div');
    t.className = 'toast ' + type;
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(function () {
      t.style.opacity = '0';
      setTimeout(function () { t.remove(); }, 300);
    }, 3200);
  };

  window.getCsrfToken = function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    if (window.CSRF_TOKEN) return window.CSRF_TOKEN;
    return '';
  };

  window.apiFetch = async function (url, options) {
    options = options || {};
    var method = (options.method || 'GET').toUpperCase();
    var headers = Object.assign({}, options.headers || {});

    var isFormData = (typeof FormData !== 'undefined') && (options.body instanceof FormData);
    if (!isFormData && options.body && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
      var csrf = window.getCsrfToken();
      if (csrf) headers['X-CSRF-Token'] = csrf;
    }

    options.headers = headers;
    options.credentials = options.credentials || 'same-origin';

    var res = await fetch(url, options);
    var data = null;
    var ct = res.headers.get('content-type') || '';
    try {
      if (ct.indexOf('application/json') !== -1) {
        data = await res.json();
      } else {
        data = { raw: await res.text() };
      }
    } catch (e) { /* ignore */ }

    if (!res.ok) {
      var err = new Error((data && (data.error || data.message)) || ('HTTP ' + res.status));
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  };

  document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.getElementById('navToggle');
    var links  = document.getElementById('navLinks');
    if (toggle && links) {
      toggle.addEventListener('click', function () { links.classList.toggle('open'); });
    }
    var logout = document.getElementById('logoutBtn');
    if (logout) {
      logout.addEventListener('click', async function () {
        try { await window.apiFetch('/api/auth/logout', { method: 'POST' }); } catch (e) {}
        window.location.href = '/login';
      });
    }
    var path = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(function (a) {
      if (a.getAttribute('href') === path) a.classList.add('active');
    });
  });
})();
