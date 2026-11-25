/**
 * Reusable browser MediaRecorder controller with permission handling and playback preview.
 */

class VoiceRecorderController {
  constructor(options) {
    this.startBtn = options.startBtn;
    this.stopBtn = options.stopBtn;
    this.clearBtn = options.clearBtn;
    this.fileInputEl = options.fileInputEl || null;
    this.statusEl = options.statusEl;
    this.audioPreviewEl = options.audioPreviewEl;
    this.errorEl = options.errorEl;
    this.onRecordingReady = options.onRecordingReady || (() => {});
    this.onRecordingCleared = options.onRecordingCleared || (() => {});

    this.mediaRecorder = null;
    this.stream = null;
    this.chunks = [];
    this.recordedBlob = null;
    this.mimeType = "audio/webm";
    this.objectUrl = null;
    this.timerInterval = null;
    this.secondsElapsed = 0;

    this._bind();
  }

  _bind() {
    this.startBtn.addEventListener("click", () => this.start());
    this.stopBtn.addEventListener("click", () => this.stop());
    if (this.clearBtn) {
      this.clearBtn.addEventListener("click", () => this.clear());
    }
    if (this.fileInputEl) {
      this.fileInputEl.addEventListener("change", () => this._handleFileSelected());
    }
  }

  _handleFileSelected() {
    this._clearError();
    const file = this.fileInputEl && this.fileInputEl.files && this.fileInputEl.files[0];
    if (!file) return;

    if (file.size < 100) {
      this._showError("Selected audio file is empty or too small.");
      this.fileInputEl.value = "";
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      this._showError("Selected audio file exceeds the 10 MB limit.");
      this.fileInputEl.value = "";
      return;
    }

    this.recordedBlob = file;
    this.mimeType = (file.type || "audio/wav").split(";")[0];
    if (this.objectUrl) {
      URL.revokeObjectURL(this.objectUrl);
    }
    this.objectUrl = URL.createObjectURL(file);
    if (this.audioPreviewEl) {
      this.audioPreviewEl.src = this.objectUrl;
      this.audioPreviewEl.hidden = false;
    }
    if (this.clearBtn) {
      this.clearBtn.hidden = false;
    }
    this.statusEl.textContent = `Selected file: ${file.name} (${Math.max(
      1,
      Math.round(file.size / 1024)
    )} KB). Preview before submitting.`;
    this.onRecordingReady(this.recordedBlob, this.mimeType);
  }

  _showError(msg) {
    if (this.errorEl) {
      this.errorEl.textContent = msg;
      this.errorEl.hidden = false;
    }
  }

  _clearError() {
    if (this.errorEl) {
      this.errorEl.textContent = "";
      this.errorEl.hidden = true;
    }
  }

  _pickSupportedMimeType() {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ];
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
      return "";
    }
    return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || "";
  }

  async start() {
    this._clearError();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      this._showError(
        "Microphone recording is unavailable in this browser or non-HTTPS context."
      );
      return;
    }
    if (typeof MediaRecorder === "undefined") {
      this._showError(
        "Your browser does not support the MediaRecorder API required for voice recording."
      );
      return;
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        this._showError(
          "Microphone permission was denied. Please allow microphone access in your browser settings and try again."
        );
      } else if (err.name === "NotFoundError") {
        this._showError("No microphone device was detected on this machine.");
      } else {
        this._showError(`Unable to access microphone: ${err.message}`);
      }
      return;
    }

    this.chunks = [];
    this.recordedBlob = null;
    const preferredMime = this._pickSupportedMimeType();

    try {
      this.mediaRecorder = preferredMime
        ? new MediaRecorder(this.stream, { mimeType: preferredMime })
        : new MediaRecorder(this.stream);
    } catch (err) {
      this._stopStream();
      this._showError(`Failed to initialize audio recorder: ${err.message}`);
      return;
    }

    this.mimeType = this.mediaRecorder.mimeType || preferredMime || "audio/webm";

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        this.chunks.push(event.data);
      }
    };

    this.mediaRecorder.onerror = (event) => {
      this._stopTimer();
      this._stopStream();
      this._showError(
        `Recording error occurred: ${event.error ? event.error.message : "unknown failure"}`
      );
    };

    this.mediaRecorder.onstop = () => {
      this._stopTimer();
      this._stopStream();
      const baseMime = (this.mimeType || "audio/webm").split(";")[0];
      this.recordedBlob = new Blob(this.chunks, { type: baseMime });

      if (this.recordedBlob.size < 100) {
        this.recordedBlob = null;
        this._showError("Recording was empty. Please speak clearly and record for 2-5 seconds.");
        this.startBtn.disabled = false;
        this.stopBtn.disabled = true;
        return;
      }

      if (this.objectUrl) {
        URL.revokeObjectURL(this.objectUrl);
      }
      this.objectUrl = URL.createObjectURL(this.recordedBlob);
      if (this.audioPreviewEl) {
        this.audioPreviewEl.src = this.objectUrl;
        this.audioPreviewEl.hidden = false;
      }
      if (this.clearBtn) {
        this.clearBtn.hidden = false;
      }
      this.statusEl.textContent = `Recorded ${this.secondsElapsed}s sample (${Math.round(
        this.recordedBlob.size / 1024
      )} KB). Preview before submitting.`;
      this.startBtn.disabled = false;
      this.stopBtn.disabled = true;
      this.onRecordingReady(this.recordedBlob, baseMime);
    };

    this.secondsElapsed = 0;
    this.mediaRecorder.start(250);
    this.startBtn.disabled = true;
    this.stopBtn.disabled = false;
    this.statusEl.innerHTML = `<span class="rec-dot"></span> Recording... 0s`;
    this.timerInterval = setInterval(() => {
      this.secondsElapsed += 1;
      this.statusEl.innerHTML = `<span class="rec-dot"></span> Recording... ${this.secondsElapsed}s`;
    }, 1000);
  }

  stop() {
    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      this.mediaRecorder.stop();
    }
  }

  clear() {
    this.recordedBlob = null;
    this.chunks = [];
    if (this.objectUrl) {
      URL.revokeObjectURL(this.objectUrl);
      this.objectUrl = null;
    }
    if (this.audioPreviewEl) {
      this.audioPreviewEl.src = "";
      this.audioPreviewEl.hidden = true;
    }
    if (this.clearBtn) {
      this.clearBtn.hidden = true;
    }
    if (this.fileInputEl) {
      this.fileInputEl.value = "";
    }
    this.statusEl.textContent = "Ready to record or upload an audio file.";
    this._clearError();
    this.onRecordingCleared();
  }

  getBlob() {
    return this.recordedBlob;
  }

  _stopTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }

  _stopStream() {
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
  }
}
