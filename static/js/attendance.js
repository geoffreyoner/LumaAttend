// ============================================================
//  Attendance page — camera + verify + check in/out
// ============================================================
(function() {
  const video      = document.getElementById('video');
  const overlay    = document.getElementById('overlay');
  const startBtn   = document.getElementById('startCam');
  const stopBtn    = document.getElementById('stopCam');
  const switchBtn  = document.getElementById('switchCam');
  const statusDot  = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  const camStatus  = document.getElementById('cameraStatus');
  const faceGuide  = document.getElementById('faceGuide');
  const checkInBtn  = document.getElementById('checkInBtn');
  const checkOutBtn = document.getElementById('checkOutBtn');
  const todayRecord = document.getElementById('todayRecord');

  if (!video || !startBtn) return;

  const cam = new CameraManager(video, overlay);
  const recognizer = new FaceRecognitionClient(cam);

  function setStatus(text, type = '') {
    if (statusText) statusText.textContent = text;
    if (statusDot)  statusDot.className = 'status-dot ' + (type || '');
    if (camStatus)  camStatus.textContent = text;
  }

  startBtn.addEventListener('click', async () => {
    setStatus('Starting camera...', 'active');
    try {
      await cam.start('user');
      startBtn.classList.add('hidden');
      stopBtn.classList.remove('hidden');
      setStatus('Camera ready — position face in oval', 'active');
      recognizer.startVerifyLoop(onVerified, onVerifyError);
    } catch (e) {
      setStatus(e.message, 'error');
      showToast(e.message, 'error');
    }
  });

  stopBtn.addEventListener('click', () => {
    recognizer.stop();
    cam.stop();
    startBtn.classList.remove('hidden');
    stopBtn.classList.add('hidden');
    setStatus('Camera off');
    if (faceGuide) faceGuide.classList.remove('detected');
  });

  if (switchBtn) {
    switchBtn.addEventListener('click', async () => {
      try {
        await cam.switchCamera();
        setStatus('Camera switched', 'active');
      } catch (e) {
        showToast(e.message, 'error');
      }
    });
  }

  function onVerified(data) {
    setStatus('Recognized: ' + data.user.full_name, 'success');
    if (faceGuide) faceGuide.classList.add('detected');
    checkInBtn.disabled  = false;
    checkOutBtn.disabled = false;
  }

  function onVerifyError(msg) {
    const lower = (msg || '').toLowerCase();
    if (lower.includes('no face') || lower.includes('no match')) {
      setStatus('Looking for face...', 'active');
    } else if (lower.includes('multiple')) {
      setStatus('Multiple faces — only one person', 'error');
    } else if (lower.includes('csrf')) {
      setStatus('Session issue — please reload page', 'error');
    } else {
      setStatus(msg, 'error');
    }
    checkInBtn.disabled  = true;
    checkOutBtn.disabled = true;
    if (faceGuide) faceGuide.classList.remove('detected');
  }

  checkInBtn.addEventListener('click', async () => {
    const frame = cam.captureFrame(0.8);
    if (!frame) return showToast('Camera not ready', 'error');
    checkInBtn.disabled = true;
    setStatus('Recording check-in...', 'active');
    try {
      const data = await apiFetch('/api/attendance/check-in', {
        method: 'POST',
        body: JSON.stringify({ image: frame }),
      });
      showToast(data.message || 'Check-in recorded', 'success');
      setStatus('Checked in: ' + data.attendance.check_in, 'success');
      loadToday();
    } catch (e) {
      showToast(e.message, 'error');
      setStatus(e.message, 'error');
    } finally {
      checkInBtn.disabled = false;
    }
  });

  checkOutBtn.addEventListener('click', async () => {
    const frame = cam.captureFrame(0.8);
    if (!frame) return showToast('Camera not ready', 'error');
    checkOutBtn.disabled = true;
    setStatus('Recording check-out...', 'active');
    try {
      const data = await apiFetch('/api/attendance/check-out', {
        method: 'POST',
        body: JSON.stringify({ image: frame }),
      });
      showToast(data.message || 'Check-out recorded', 'success');
      setStatus('Checked out: ' + data.attendance.check_out, 'success');
      loadToday();
    } catch (e) {
      showToast(e.message, 'error');
      setStatus(e.message, 'error');
    } finally {
      checkOutBtn.disabled = false;
    }
  });

  async function loadToday() {
    try {
      const data = await apiFetch('/api/attendance/today');
      if (!data.today || data.today.length === 0) {
        todayRecord.innerHTML = '<p class="text-muted">No record yet</p>';
        return;
      }
      todayRecord.innerHTML = data.today.map(r => `
        <div class="record-item">
          <div><strong>${window.escapeHtml(r.full_name || r.employee_code)}</strong></div>
          <div>
            <span class="badge ${window.escapeHtml((r.status||'').split(' ')[0])}">${window.escapeHtml(r.status)}</span>
            ${r.check_in  ? 'In: '  + window.escapeHtml(r.check_in.slice(0,5))  : ''}
            ${r.check_out ? 'Out: ' + window.escapeHtml(r.check_out.slice(0,5)) : ''}
          </div>
        </div>
      `).join('');
    } catch (e) { /* ignore */ }
  }

  loadToday();
})();
