// ============================================================
//  LumaAttend — Kiosk mode
//  Auto-scan loop, wake lock, auto-reset after success.
// ============================================================
(function () {
  'use strict';

  var video       = document.getElementById('kioskVideo');
  var faceGuide   = document.getElementById('faceGuide');
  var statusEl    = document.getElementById('kioskStatus');
  var statusDot   = document.getElementById('statusDot');
  var statusText  = document.getElementById('statusText');
  var successEl   = document.getElementById('kioskSuccess');
  var successName = document.getElementById('successName');
  var successAct  = document.getElementById('successAction');
  var successTime = document.getElementById('successTime');
  var clockEl     = document.getElementById('kioskClock');
  var errorEl     = document.getElementById('kioskError');

  if (!video) { console.error('kiosk: no video element'); return; }
  if (typeof CameraManager !== 'function') {
    showError('camera.js not loaded');
    return;
  }

  var cam = new CameraManager(video, null);
  var scanning = true;
  var paused = false;
  var fps = 3;
  var lastFrame = 0;
  var errors = 0;
  var wakeLock = null;
  var successTimer = null;
  var scanPausedUntil = 0;

  // ----- Clock -----
  function tickClock() {
    var d = new Date();
    var hh = String(d.getHours()).padStart(2, '0');
    var mm = String(d.getMinutes()).padStart(2, '0');
    var ss = String(d.getSeconds()).padStart(2, '0');
    clockEl.textContent = hh + ':' + mm + ':' + ss;
  }
  tickClock();
  setInterval(tickClock, 1000);

  // ----- Status -----
  function setStatus(text, state) {
    statusText.textContent = text;
    statusDot.className = 'kiosk-status-dot ' + (state || '');
  }
  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.classList.add('show');
    setTimeout(function () { errorEl.classList.remove('show'); }, 6000);
  }

  // ----- Wake Lock (keep screen on) -----
  async function requestWakeLock() {
    try {
      if ('wakeLock' in navigator) {
        wakeLock = await navigator.wakeLock.request('screen');
        wakeLock.addEventListener('release', function () {
          console.log('[kiosk] Wake lock released');
          wakeLock = null;
        });
        console.log('[kiosk] Wake lock acquired');
      }
    } catch (e) {
      console.warn('[kiosk] Wake lock unavailable:', e.message);
    }
  }

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
      requestWakeLock();
      if (!cam.active) startKiosk();
    }
  });

  // ----- Audio beep (best-effort) -----
  var audioCtx = null;
  function ensureAudio() {
    if (audioCtx) return audioCtx;
    try {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) audioCtx = new Ctx();
    } catch (e) {}
    return audioCtx;
  }
  function beep(freq) {
    var ctx = ensureAudio();
    if (!ctx) return;
    try {
      if (ctx.state === 'suspended') ctx.resume();
      var o = ctx.createOscillator();
      var g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.type = 'sine';
      o.frequency.value = freq || 880;
      g.gain.setValueAtTime(0.0001, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
      o.start();
      o.stop(ctx.currentTime + 0.3);
    } catch (e) {}
  }
  // Resume audio on first tap (browser policy)
  document.addEventListener('touchstart', function once() {
    ensureAudio();
    if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
    document.removeEventListener('touchstart', once);
  }, { once: true });

  // ----- Start camera -----
  async function startKiosk() {
    setStatus('Menyalakan kamera...', 'active');
    try {
      await cam.start('user');
      setStatus('Hadapkan wajah ke kamera', 'active');
      scanning = true;
      loop();
    } catch (e) {
      setStatus('Kamera gagal', 'error');
      showError(e.message);
      // Retry after 5s
      setTimeout(startKiosk, 5000);
    }
  }

  // ----- Scan loop -----
  async function loop() {
    if (!scanning) return;

    if (paused || performance.now() < scanPausedUntil) {
      setTimeout(loop, 300);
      return;
    }

    var now = performance.now();
    if (now - lastFrame >= 1000 / fps) {
      lastFrame = now;
      var frame = cam.captureFrame(0.72);

      if (frame) {
        try {
          var res = await fetch('/api/kiosk/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: frame })
          });
          var data = await res.json();
          errors = 0;

          if (data.matched && data.user) {
            onMatch(data);
            return;
          }
          if (data.cooldown) {
            setStatus(data.message || 'Tunggu sebentar...', 'active');
            scanPausedUntil = performance.now() + 1200;
          }

          // Not matched yet
          var msg = (data.message || '').toLowerCase();
          if (msg.indexOf('no face') !== -1) {
            setStatus('Hadapkan wajah ke kamera', 'active');
            faceGuide.classList.remove('detected');
          } else if (msg.indexOf('multiple') !== -1) {
            setStatus('Satu orang saja di depan kamera', 'warn');
            faceGuide.classList.remove('detected');
          } else if (msg.indexOf('belum ada wajah') !== -1) {
            setStatus('Belum ada wajah terdaftar', 'warn');
            faceGuide.classList.remove('detected');
          } else if (msg.indexOf('not recognized') !== -1 || msg.indexOf('no match') !== -1) {
            setStatus('Wajah tidak dikenali — coba lagi', 'warn');
            faceGuide.classList.remove('detected');
            scanPausedUntil = performance.now() + 1500;
          } else {
            setStatus(data.message || 'Menunggu...', 'active');
          }
        } catch (e) {
          errors++;
          if (errors === 3) {
            setStatus('Server tidak merespons', 'error');
          }
          if (errors > 8) {
            scanPausedUntil = performance.now() + 3000;
            errors = 0;
          }
        }
      }
    }
    setTimeout(loop, 100);
  }

  // ----- Success handling -----
  function onMatch(data) {
    paused = true;
    faceGuide.classList.add('success');
    faceGuide.classList.add('detected');

    var u = data.user || {};
    var action = data.action || 'check-in';
    var time = data.time || new Date().toLocaleTimeString('id-ID');
    var status = data.status || '';

    successName.textContent = u.full_name || u.employee_code || '-';

    if (action === 'check-in') {
      successAct.textContent = 'Check-in berhasil';
      beep(880);
    } else if (action === 'check-out') {
      successAct.textContent = 'Check-out berhasil';
      beep(660);
    } else if (action === 'already-complete') {
      successAct.textContent = 'Sudah lengkap hari ini';
      beep(440);
    } else if (action === 'waiting-checkout') {
      successAct.textContent = data.message || 'Check-out belum tersedia';
      beep(440);
    } else {
      successAct.textContent = action;
      beep(880);
    }

    successTime.textContent = time + (status ? '  ·  ' + status : '');
    successEl.classList.add('show');
    setStatus('Terima kasih, ' + (u.full_name || ''), 'success');

    var resetMs = action === 'already-complete' || action === 'waiting-checkout' ? 4500 : 4000;
    clearTimeout(successTimer);
    successTimer = setTimeout(function () {
      successEl.classList.remove('show');
      faceGuide.classList.remove('success');
      faceGuide.classList.remove('detected');
      paused = false;
      setStatus('Hadapkan wajah ke kamera', 'active');
      loop();
    }, resetMs);
  }

  // ----- Init -----
  requestWakeLock();
  window.addEventListener('load', function () {
    setTimeout(startKiosk, 400);
  });

  window.addEventListener('pagehide', function () {
    if (cam) cam.stop();
  });
})();