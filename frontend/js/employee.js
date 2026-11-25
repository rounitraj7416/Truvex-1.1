/**
 * Employee Dashboard controller: profile, voice enrollment, pre-call verification, and Trust ID issuance.
 */

(() => {
  let profile = null;
  let allPurposes = [];
  let isMockProvider = true;
  let enrollRecorder = null;
  let precallRecorder = null;

  function renderProfile(emp) {
    profile = emp;
    document.getElementById("emp-header-name").textContent = emp.full_name;
    document.getElementById("emp-header-meta").textContent = `${emp.designation} • ${emp.department} • ${emp.company_name} (${emp.employee_code})`;
    document.getElementById("emp-company-status").innerHTML = TrustAPI.statusBadge(emp.company_status);
    document.getElementById("emp-identity-status").innerHTML = TrustAPI.statusBadge(emp.identity_status);
    document.getElementById("emp-voice-status").innerHTML = emp.voice_enrolled
      ? TrustAPI.statusBadge("ENROLLED")
      : TrustAPI.statusBadge("NOT ENROLLED");

    const purposesContainer = document.getElementById("emp-allowed-purposes");
    purposesContainer.innerHTML = (emp.allowed_purposes || []).length
      ? emp.allowed_purposes
          .map((p) => `<span class="badge badge-blue" style="margin:2px;">${TrustAPI.escapeHtml(p)}</span>`)
          .join(" ")
      : `<span class="form-hint">No communication purposes assigned.</span>`;

    const enrollmentMetaEl = document.getElementById("enrollment-metadata-box");
    if (emp.latest_enrollment) {
      const le = emp.latest_enrollment;
      enrollmentMetaEl.hidden = false;
      enrollmentMetaEl.innerHTML = `
        <strong>Latest Voice Enrollment:</strong> ${TrustAPI.statusBadge(le.status)}
        <div class="form-hint">Provider: <span class="mono">${TrustAPI.escapeHtml(le.provider)}</span> • Enrolled at ${TrustAPI.formatDateTime(le.enrolled_at)}</div>
        ${
          le.is_mock
            ? `<div class="alert alert-warning" style="margin-top:0.6rem;margin-bottom:0;">DEMO MODE — Voice enrollment simulated using a mock provider. No real biometric voiceprint was stored.</div>`
            : ""
        }
      `;
    } else {
      enrollmentMetaEl.hidden = true;
    }

    // Populate purpose dropdown (show assigned first, plus unassigned clearly labeled for backend enforcement testability)
    const selectEl = document.getElementById("precall-purpose");
    const assigned = new Set(emp.allowed_purposes || []);
    selectEl.innerHTML = allPurposes
      .map((p) => {
        const ok = assigned.has(p);
        return `<option value="${TrustAPI.escapeHtml(p)}">${TrustAPI.escapeHtml(p)}${
          ok ? " (Authorized)" : " (Not Assigned — Will Fail Layer 4)"
        }</option>`;
      })
      .join("");
    const firstAssigned = allPurposes.find((p) => assigned.has(p));
    if (firstAssigned) selectEl.value = firstAssigned;

    const precallWarning = document.getElementById("precall-prereq-warning");
    if (emp.company_status !== "VERIFIED") {
      precallWarning.hidden = false;
      precallWarning.textContent = `Company status is ${emp.company_status}. Pre-call verification is blocked until your company is VERIFIED.`;
    } else if (!emp.voice_enrolled) {
      precallWarning.hidden = false;
      precallWarning.textContent =
        "Complete voice enrollment above before generating a pre-call Trust ID.";
    } else {
      precallWarning.hidden = true;
    }
  }

  function renderSessions(sessions) {
    const tbody = document.getElementById("emp-sessions-tbody");
    if (!sessions.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No pre-call sessions issued yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = sessions
      .map(
        (s) => `
      <tr>
        <td><strong>${TrustAPI.escapeHtml(s.purpose)}</strong>${
          s.reference_note ? `<div class="form-hint">${TrustAPI.escapeHtml(s.reference_note)}</div>` : ""
        }</td>
        <td>${TrustAPI.statusBadge(s.status)}</td>
        <td class="mono">${TrustAPI.escapeHtml(s.ai_provider)}${
          s.is_mock ? ' <span class="badge badge-amber">MOCK</span>' : ""
        }</td>
        <td>
          <div class="form-hint">Issued: ${TrustAPI.formatDateTime(s.issued_at)}</div>
          <div class="form-hint">Expires: ${TrustAPI.formatDateTime(s.expires_at)}</div>
        </td>
        <td>${
          s.suspicious_report_count > 0
            ? `<span class="badge badge-red">${s.suspicious_report_count} Flagged</span>`
            : '<span class="badge badge-slate">None</span>'
        }</td>
      </tr>`
      )
      .join("");
  }

  function renderVerificationOutcome(result) {
    const outBox = document.getElementById("precall-result-box");
    outBox.hidden = false;

    const layersHtml = (result.layer_results || [])
      .map(
        (lr) => `
      <div class="layer-item ${lr.passed ? "pass" : "fail"}">
        <div>
          <strong>${TrustAPI.escapeHtml(lr.layer)}</strong>
          <div class="form-hint">${TrustAPI.escapeHtml(lr.message)}</div>
        </div>
        <div>${TrustAPI.statusBadge(lr.passed ? lr.status : lr.status)}</div>
      </div>`
      )
      .join("");

    const mockBanner = result.is_mock
      ? `<div class="alert alert-warning">${TrustAPI.escapeHtml(
          result.mock_notice ||
            "DEMO MODE — AI assessment simulated using a mock provider. No real deepfake detection was performed."
        )}</div>`
      : "";

    if (result.issued && result.trust_id) {
      const verifyUrl = `${window.location.origin}/verify.html?id=${encodeURIComponent(
        result.trust_id
      )}`;
      outBox.innerHTML = `
        ${mockBanner}
        <div class="trust-id-box">
          <div style="font-size:0.82rem;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;">Single-Use Trust ID Issued</div>
          <div class="trust-id-code" id="issued-trust-id">${TrustAPI.escapeHtml(result.trust_id)}</div>
          <div style="font-size:0.85rem;color:#cbd5e1;margin-bottom:0.85rem;">
            Purpose: <strong>${TrustAPI.escapeHtml(result.purpose)}</strong> • Expires: ${TrustAPI.formatDateTime(
        result.expires_at
      )}
          </div>
          <div style="display:flex;gap:0.6rem;justify-content:center;flex-wrap:wrap;">
            <button type="button" class="btn btn-primary btn-sm" id="copy-trust-id-btn">Copy Trust ID</button>
            <a href="${verifyUrl}" target="_blank" rel="noopener" class="btn btn-outline-light btn-sm">Open Customer Verification Page</a>
          </div>
        </div>
        <h3 style="margin:1rem 0 0.4rem;font-size:0.95rem;">Five Independent Trust Layer Results</h3>
        <div class="layer-list">${layersHtml}</div>
      `;

      document.getElementById("copy-trust-id-btn").addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(result.trust_id);
          TrustAPI.showToast("Trust ID copied to clipboard.", "success");
        } catch {
          TrustAPI.showToast("Copy failed; please select the ID manually.", "error");
        }
      });
    } else {
      outBox.innerHTML = `
        ${mockBanner}
        <div class="alert alert-danger">
          <strong>Pre-Call Verification Denied:</strong> One or more mandatory trust layers failed. No Trust ID was generated.
        </div>
        <div class="layer-list">${layersHtml}</div>
      `;
    }
  }

  async function refreshEmployeeData() {
    const [emp, sessionsData] = await Promise.all([
      TrustAPI.request("/api/employees/me"),
      TrustAPI.request("/api/employees/me/sessions"),
    ]);
    renderProfile(emp);
    renderSessions(sessionsData.sessions || []);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const user = await TrustAuth.requireAuth(["employee"]);
    if (!user) return;
    document.getElementById("nav-user-label").textContent = user.full_name;

    const [health, purposesRes] = await Promise.all([
      TrustAPI.getHealth(),
      TrustAPI.request("/api/employees/purposes"),
    ]);
    isMockProvider = Boolean(health.is_mock_ai);
    allPurposes = purposesRes.purposes || [];

    if (isMockProvider) {
      document.getElementById("global-mock-banner").hidden = false;
      document.getElementById("demo-sim-group").hidden = false;
    } else {
      const liveBanner = document.getElementById("global-live-ai-banner");
      if (liveBanner) liveBanner.hidden = false;
    }

    await refreshEmployeeData();

    enrollRecorder = new VoiceRecorderController({
      startBtn: document.getElementById("enroll-rec-start"),
      stopBtn: document.getElementById("enroll-rec-stop"),
      clearBtn: document.getElementById("enroll-rec-clear"),
      fileInputEl: document.getElementById("enroll-file-input"),
      statusEl: document.getElementById("enroll-rec-status"),
      audioPreviewEl: document.getElementById("enroll-audio-preview"),
      errorEl: document.getElementById("enroll-rec-error"),
      onRecordingReady: () => {
        document.getElementById("enroll-submit-btn").disabled = false;
      },
      onRecordingCleared: () => {
        document.getElementById("enroll-submit-btn").disabled = true;
      },
    });

    precallRecorder = new VoiceRecorderController({
      startBtn: document.getElementById("precall-rec-start"),
      stopBtn: document.getElementById("precall-rec-stop"),
      clearBtn: document.getElementById("precall-rec-clear"),
      fileInputEl: document.getElementById("precall-file-input"),
      statusEl: document.getElementById("precall-rec-status"),
      audioPreviewEl: document.getElementById("precall-audio-preview"),
      errorEl: document.getElementById("precall-rec-error"),
      onRecordingReady: () => {
        document.getElementById("precall-submit-btn").disabled = false;
      },
      onRecordingCleared: () => {
        document.getElementById("precall-submit-btn").disabled = true;
      },
    });

    document.getElementById("voice-enroll-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = document.getElementById("enroll-submit-error");
      errEl.hidden = true;

      const consent = document.getElementById("enroll-consent-checkbox").checked;
      if (!consent) {
        errEl.textContent = "You must check the consent confirmation box before enrolling your voice.";
        errEl.hidden = false;
        return;
      }

      const blob = enrollRecorder.getBlob();
      if (!blob) {
        errEl.textContent = "Please record a voice sample before submitting.";
        errEl.hidden = false;
        return;
      }

      const btn = document.getElementById("enroll-submit-btn");
      btn.disabled = true;
      btn.textContent = "Enrolling...";

      const formData = new FormData();
      formData.append("consent", "true");
      formData.append("audio", blob, blob.name || "voice-enrollment.webm");

      try {
        await TrustAPI.request("/api/verification/voice-enroll", {
          method: "POST",
          body: formData,
        });
        TrustAPI.showToast("Voice enrollment recorded successfully.", "success");
        enrollRecorder.clear();
        await refreshEmployeeData();
      } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
      } finally {
        btn.disabled = !enrollRecorder.getBlob();
        btn.textContent = "Submit Voice Enrollment";
      }
    });

    document.getElementById("precall-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = document.getElementById("precall-submit-error");
      errEl.hidden = true;

      const blob = precallRecorder.getBlob();
      if (!blob) {
        errEl.textContent = "Record a fresh voice sample before initiating pre-call verification.";
        errEl.hidden = false;
        return;
      }

      const btn = document.getElementById("precall-submit-btn");
      btn.disabled = true;
      btn.textContent = "Evaluating 5 Trust Layers...";

      const formData = new FormData();
      formData.append("purpose", document.getElementById("precall-purpose").value);
      const refNote = document.getElementById("precall-note").value.trim();
      if (refNote) formData.append("reference_note", refNote);

      const simSelect = document.getElementById("precall-sim-mode");
      if (isMockProvider && simSelect && simSelect.value !== "normal") {
        formData.append("simulation_mode", simSelect.value);
      }
      formData.append("audio", blob, blob.name || "precall-sample.webm");

      try {
        const res = await fetch("/api/verification/pre-call", {
          method: "POST",
          credentials: "same-origin",
          body: formData,
        });
        const data = await res.json();
        if (data && data.layer_results) {
          renderVerificationOutcome(data);
          if (data.issued) {
            TrustAPI.showToast("Trust ID issued!", "success");
          } else {
            TrustAPI.showToast("Verification check failed. Trust ID denied.", "error");
          }
          await refreshEmployeeData();
        } else {
          throw new Error(data.detail || "Pre-call verification failed.");
        }
      } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
      } finally {
        btn.disabled = !precallRecorder.getBlob();
        btn.textContent = "Run Verification & Issue Trust ID";
      }
    });
  });
})();
