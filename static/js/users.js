(function () {
  'use strict';

  // Defensive: ensure apiFetch exists
  if (typeof window.apiFetch !== 'function') {
    console.error('[users.js] apiFetch missing — app.js failed to load');
    var el = document.getElementById('usersList');
    if (el) el.innerHTML = '<p class="text-muted">Error: apiFetch not loaded. Reload the page (Ctrl+Shift+R).</p>';
    return;
  }

  var listEl   = document.getElementById('usersList');
  var searchEl = document.getElementById('userSearch');
  var modal    = document.getElementById('userModal');
  var form     = document.getElementById('userForm');
  var faceModal = document.getElementById('faceModal');
  var regCam = null;
  var currentFaceUser = null;

  async function loadUsers(q) {
    q = q || '';
    listEl.innerHTML = '<p class="text-muted">Loading...</p>';
    try {
      var data = await apiFetch('/api/users' + (q ? '?q=' + encodeURIComponent(q) : ''));
      if (!data.users.length) {
        listEl.innerHTML = '<p class="text-muted">No users found</p>';
        return;
      }
      listEl.innerHTML = data.users.map(function (u) {
        return '<div class="user-card" data-id="' + u.id + '">' +
          '<h4>' + window.escapeHtml(u.full_name) + '</h4>' +
          '<div class="meta">' + window.escapeHtml(u.employee_code) + ' · @' + window.escapeHtml(u.username) + ' · ' + window.escapeHtml(u.role) + '</div>' +
          '<div class="meta">' + (u.has_face ? '<span class="tag">Face ✓</span>' : '<span class="tag">No face</span>') +
          (u.is_active ? '' : ' <span class="tag">Inactive</span>') + '</div>' +
          '<div class="actions">' +
            '<button class="btn btn-sm btn-outline" data-act="edit">Edit</button>' +
            '<button class="btn btn-sm btn-outline" data-act="face">Register Face</button>' +
            '<button class="btn btn-sm btn-ghost" data-act="delface">Delete Face</button>' +
          '</div>' +
        '</div>';
      }).join('');
    } catch (e) {
      listEl.innerHTML = '<p class="text-muted">Error: ' + window.escapeHtml(e.message) + '</p>';
    }
  }

  listEl.addEventListener('click', async function (e) {
    var btn = e.target.closest('button[data-act]');
    if (!btn) return;
    var card = btn.closest('.user-card');
    var uid = card.dataset.id;
    var act = btn.dataset.act;

    if (act === 'edit') {
      var data = await apiFetch('/api/users/' + uid);
      openUserModal(data.user);
    } else if (act === 'face') {
      currentFaceUser = uid;
      document.getElementById('faceUserName').textContent = card.querySelector('h4').textContent;
      faceModal.classList.remove('hidden');
      await new Promise(function (r) { requestAnimationFrame(function () { setTimeout(r, 200); }); });
      await openRegCamera();
    } else if (act === 'delface') {
      if (!confirm('Delete face template for this user?')) return;
      await apiFetch('/api/users/' + uid, { method: 'DELETE' });
      showToast('Face template deleted', 'success');
      loadUsers(searchEl.value);
    }
  });

  document.getElementById('addUserBtn').addEventListener('click', function () { openUserModal(null); });
  document.getElementById('cancelUser').addEventListener('click', function () { modal.classList.add('hidden'); });

  function openUserModal(user) {
    document.getElementById('modalTitle').textContent = user ? 'Edit User' : 'Add User';
    document.getElementById('userId').value = user ? user.id : '';
    document.getElementById('empCode').value  = user ? user.employee_code : '';
    document.getElementById('fullName').value = user ? user.full_name : '';
    document.getElementById('username').value = user ? user.username : '';
    document.getElementById('password').value = '';
    document.getElementById('role').value = user ? user.role : 'employee';
    modal.classList.remove('hidden');
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var uid = document.getElementById('userId').value;
    var payload = {
      employee_code: document.getElementById('empCode').value.trim(),
      full_name: document.getElementById('fullName').value.trim(),
      username: document.getElementById('username').value.trim(),
      role: document.getElementById('role').value
    };
    var pass = document.getElementById('password').value;
    if (pass) payload.password = pass;
    try {
      if (uid) {
        await apiFetch('/api/users/' + uid, { method: 'PUT', body: JSON.stringify(payload) });
        showToast('User updated', 'success');
      } else {
        if (!pass) { showToast('Password required for new user', 'error'); return; }
        payload.password = pass;
        await apiFetch('/api/users', { method: 'POST', body: JSON.stringify(payload) });
        showToast('User created', 'success');
      }
      modal.classList.add('hidden');
      loadUsers(searchEl.value);
    } catch (e) { showToast(e.message, 'error'); }
  });

  async function openRegCamera() {
    var video = document.getElementById('regVideo');
    if (!video) { showToast('Video element missing', 'error'); return; }
    if (typeof CameraManager !== 'function') {
      showToast('camera.js not loaded — reload page', 'error');
      return;
    }
    if (regCam) { regCam.stop(); regCam = null; }
    regCam = new CameraManager(video, null);
    try {
      await regCam.start('user');
      try { await video.play(); } catch (e) {}
    } catch (e) {
      console.error('[RegCam]', e);
      showToast('Camera: ' + e.message, 'error');
    }
  }

  document.getElementById('cancelFace').addEventListener('click', function () {
    if (regCam) { regCam.stop(); regCam = null; }
    faceModal.classList.add('hidden');
  });

  document.getElementById('captureFace').addEventListener('click', async function () {
    if (!regCam || !regCam.active) { showToast('Camera not ready', 'error'); return; }
    var frame = regCam.captureFrame(0.85);
    if (!frame) { showToast('Camera frame empty', 'error'); return; }
    try {
      await apiFetch('/api/face/register', {
        method: 'POST',
        body: JSON.stringify({ user_id: currentFaceUser, image: frame })
      });
      showToast('Face registered successfully', 'success');
      if (regCam) { regCam.stop(); regCam = null; }
      faceModal.classList.add('hidden');
      loadUsers(searchEl.value);
    } catch (e) { showToast(e.message, 'error'); }
  });

  var searchTimer;
  searchEl.addEventListener('input', function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () { loadUsers(searchEl.value.trim()); }, 300);
  });

  loadUsers();
})();
