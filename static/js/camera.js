class CameraManager {
  constructor(videoEl, canvasEl) {
    this.video = videoEl;
    this.canvas = canvasEl;
    this.ctx = canvasEl ? canvasEl.getContext('2d') : null;
    this.stream = null;
    this.facingMode = 'user';
    this.active = false;
  }

  async start(facingMode = 'user') {
    this.facingMode = facingMode;
    if (this.stream) this.stop();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('Camera API not available (browser requires HTTPS or localhost).');
    }

    const constraints = {
      audio: false,
      video: {
        facingMode: { ideal: this.facingMode },
        width:  { ideal: 640 },
        height: { ideal: 480 },
      },
    };

    try {
      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (e) {
      throw new Error(this._friendlyError(e));
    }

    this.video.srcObject = this.stream;
    this.video.setAttribute('playsinline', '');
    this.video.setAttribute('autoplay', '');
    this.video.muted = true;

    // Wait for metadata so videoWidth/Height are known
    await new Promise((resolve) => {
      if (this.video.readyState >= 2) return resolve();
      const onMeta = () => { this.video.removeEventListener('loadedmetadata', onMeta); resolve(); };
      this.video.addEventListener('loadedmetadata', onMeta);
      setTimeout(resolve, 1500); // safety timeout
    });

    // Try to play; retry once after a short delay if it fails
    try {
      await this.video.play();
    } catch (e) {
      console.warn('[Camera] play() failed, retrying:', e.message);
      await new Promise(r => setTimeout(r, 200));
      try { await this.video.play(); }
      catch (e2) { throw new Error('Cannot start video playback: ' + e2.message); }
    }

    this.active = true;
    if (this.canvas) {
      this.canvas.width  = this.video.videoWidth  || 640;
      this.canvas.height = this.video.videoHeight || 480;
    }
    return true;
  }

  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
    try { this.video.pause(); } catch(e) {}
    this.video.srcObject = null;
    this.active = false;
    if (this.ctx) this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  switchCamera() {
    return this.start(this.facingMode === 'user' ? 'environment' : 'user');
  }

  captureFrame(quality = 0.75) {
    if (!this.active) return null;
    const w = this.video.videoWidth;
    const h = this.video.videoHeight;
    if (!w || !h) return null;
    const tmp = document.createElement('canvas');
    const maxW = 480;
    const scale = Math.min(1, maxW / w);
    tmp.width  = Math.round(w * scale);
    tmp.height = Math.round(h * scale);
    const tctx = tmp.getContext('2d');
    tctx.drawImage(this.video, 0, 0, tmp.width, tmp.height);
    return tmp.toDataURL('image/jpeg', quality);
  }

  drawBox(box, color = '#55D6A7') {
    if (!this.ctx) return;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    if (!box) return;
    const sx = this.canvas.width  / (this.video.videoWidth  || this.canvas.width);
    const sy = this.canvas.height / (this.video.videoHeight || this.canvas.height);
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = 3;
    this.ctx.strokeRect(box.x * sx, box.y * sy, box.w * sx, box.h * sy);
  }

  _friendlyError(e) {
    if (e.name === 'NotAllowedError') return 'Camera permission denied. Allow camera in browser settings.';
    if (e.name === 'NotFoundError') return 'No camera found on this device.';
    if (e.name === 'NotReadableError') return 'Camera is in use by another app or tab. Close other camera tabs.';
    if (e.name === 'OverconstrainedError') return 'Camera does not support requested settings.';
    return 'Camera error: ' + (e.message || e.name);
  }
}
