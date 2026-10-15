class FaceRecognitionClient {
  constructor(cameraManager) {
    this.cam = cameraManager;
    this.processing = false;
    this.fps = 4;
    this._lastFrame = 0;
    this._lastErrorAt = 0;
    this._consecutiveErrors = 0;
    this._pausedUntil = 0;
  }

  setFps(fps) {
    this.fps = Math.max(1, Math.min(10, parseInt(fps) || 4));
  }

  startVerifyLoop(onResult, onError) {
    this.processing = true;
    this._consecutiveErrors = 0;
    this._pausedUntil = 0;

    const loop = async () => {
      if (!this.processing) return;

      if (performance.now() < this._pausedUntil) {
        setTimeout(loop, 500);
        return;
      }

      const now = performance.now();
      if (now - this._lastFrame >= 1000 / this.fps) {
        this._lastFrame = now;
        const frame = this.cam.captureFrame(0.7);

        if (frame) {
          try {
            const data = await window.apiFetch('/api/face/verify', {
              method: 'POST',
              body: JSON.stringify({ image: frame }),
            });
            this._consecutiveErrors = 0;

            if (data && data.matched && data.user) {
              onResult(data);
            } else if (data && data.error) {
              onError(data.error);
            } else if (data && data.message) {
              onError(data.message);
            } else {
              onError('No face match');
            }
          } catch (e) {
            this._consecutiveErrors++;
            const t = performance.now();

            if (t - this._lastErrorAt > 2000) {
              this._lastErrorAt = t;
              onError(e.message || 'Recognition error');
            }

            if (e.status === 403) {
              this._pausedUntil = performance.now() + 5000;
            } else if (this._consecutiveErrors >= 5) {
              this._pausedUntil = performance.now() + 3000;
              this._consecutiveErrors = 0;
            }
          }
        }
      }
      setTimeout(loop, 100);
    };
    loop();
  }

  stop() {
    this.processing = false;
  }
}