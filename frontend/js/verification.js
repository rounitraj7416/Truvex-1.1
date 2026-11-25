/**
 * Public Customer Verification Page controller.
 */

(() => {
  function statusBannerClass(overallStatus) {
    const s = String(overallStatus || "").toLowerCase();
    if (s === "verified") return "verified";
    if (s === "suspicious") return "suspicious";
    if (s === "expired") return "expired";
    return "invalid";
  }

  function renderVerificationResult(data) {
    const resultSection = document.getElementById("verification-result");
    resultSection.hidden = false;

    const bannerEl = document.getElementById("overall-status-banner");
    bannerEl.className = `verify-status-banner ${statusBannerClass(data.overall_status)}`;
    bannerEl.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;">
        <div>
          <div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">Overall Verification Status</div>
          <h2 style="margin:0.15rem 0 0.35rem;font-size:1.55rem;">${TrustAPI.escapeHtml(
            data.overall_status
          )}</h2>
        </div>
        ${
          data.customer_session_active
            ? '<button type="button" class="btn btn-secondary btn-sm" id="verify-another-btn">Verify Another Trust ID</button>'
            : ""
        }
      </div>
      <p style="margin:0;font-size:0.95rem;">${TrustAPI.escapeHtml(data.status_explanation)}</p>
    `;

    const verifyAnotherBtn = document.getElementById("verify-another-btn");
    if (verifyAnotherBtn) {
      verifyAnotherBtn.addEventListener("click", async () => {
        await TrustAPI.request("/api/public/session/clear", { method: "POST" });
        resultSection.hidden = true;
        document.getElementById("trust-id-input").value = "";
        document.getElementById("lookup-card").hidden = false;
      });
    }

    const detailsGrid = document.getElementById("verification-details-grid");
    if (!data.company || !data.employee || !data.ai_assessment || !data.communication) {
      detailsGrid.hidden = true;
      document.getElementById("report-card").hidden = true;
      return;
    }

    detailsGrid.hidden = false;

    document.getElementById("verify-company-kv").innerHTML = `
      <div class="kv-row"><dt>Company Name</dt><dd>${TrustAPI.escapeHtml(data.company.company_name)}</dd></div>
      <div class="kv-row"><dt>Verification Status</dt><dd>${TrustAPI.statusBadge(data.company.verification_status)}</dd></div>
      <div class="kv-row"><dt>Industry</dt><dd>${TrustAPI.escapeHtml(data.company.industry)}</dd></div>
      <div class="kv-row"><dt>Verification Indicator</dt><dd>${TrustAPI.escapeHtml(data.company.verification_indicator)}</dd></div>
    `;

    document.getElementById("verify-employee-kv").innerHTML = `
      <div class="kv-row"><dt>Employee Name</dt><dd>${TrustAPI.escapeHtml(data.employee.full_name)}</dd></div>
      <div class="kv-row"><dt>Designation</dt><dd>${TrustAPI.escapeHtml(data.employee.designation)}</dd></div>
      <div class="kv-row"><dt>Department</dt><dd>${TrustAPI.escapeHtml(data.employee.department)}</dd></div>
      <div class="kv-row"><dt>Authorization Status</dt><dd>${TrustAPI.statusBadge(data.employee.authorization_status)}</dd></div>
      <div class="kv-row"><dt>Company Association</dt><dd>${TrustAPI.escapeHtml(data.employee.company_association)}</dd></div>
    `;

    const ai = data.ai_assessment;
    const mockNoticeEl = document.getElementById("public-mock-notice");
    if (ai.is_mock) {
      mockNoticeEl.hidden = false;
      mockNoticeEl.textContent =
        ai.mock_notice ||
        "DEMO MODE — AI assessment simulated using a mock provider. No real deepfake detection was performed.";
    } else {
      mockNoticeEl.hidden = true;
    }

    document.getElementById("verify-ai-kv").innerHTML = `
      <div class="kv-row"><dt>Voice Verification</dt><dd>${TrustAPI.statusBadge(ai.voice_verification_decision)}</dd></div>
      <div class="kv-row"><dt>Voice Match Score</dt><dd>${
        ai.voice_match_score !== null && ai.voice_match_score !== undefined
          ? `${(ai.voice_match_score * 100).toFixed(1)}%`
          : "N/A"
      }</dd></div>
      <div class="kv-row"><dt>Deepfake Assessment</dt><dd>${TrustAPI.statusBadge(ai.deepfake_decision)}</dd></div>
      <div class="kv-row"><dt>Deepfake Risk Score</dt><dd>${
        ai.deepfake_risk_score !== null && ai.deepfake_risk_score !== undefined
          ? `${(ai.deepfake_risk_score * 100).toFixed(1)}%`
          : "N/A"
      }</dd></div>
      <div class="kv-row"><dt>Assessment Time</dt><dd>${TrustAPI.formatDateTime(ai.assessment_timestamp)}</dd></div>
      <div class="kv-row"><dt>AI Provider</dt><dd class="mono">${TrustAPI.escapeHtml(ai.provider_name)}</dd></div>
    `;

    const comm = data.communication;
    document.getElementById("verify-comm-kv").innerHTML = `
      <div class="kv-row"><dt>Stated Purpose</dt><dd>${TrustAPI.escapeHtml(comm.purpose)}</dd></div>
      ${
        comm.reference_note
          ? `<div class="kv-row"><dt>Reference Note</dt><dd>${TrustAPI.escapeHtml(comm.reference_note)}</dd></div>`
          : ""
      }
      <div class="kv-row"><dt>Session Issue Time</dt><dd>${TrustAPI.formatDateTime(comm.issued_at)}</dd></div>
      <div class="kv-row"><dt>Expiry Time</dt><dd>${TrustAPI.formatDateTime(comm.expires_at)}</dd></div>
      <div class="kv-row"><dt>Session Validity</dt><dd>${TrustAPI.escapeHtml(comm.session_validity)}</dd></div>
    `;

    const reportCard = document.getElementById("report-card");
    if (data.customer_session_active) {
      reportCard.hidden = false;
      const formWrap = document.getElementById("report-form-wrap");
      const alreadyWrap = document.getElementById("report-already-submitted");
      if (data.suspicious_reported) {
        formWrap.hidden = true;
        alreadyWrap.hidden = false;
      } else {
        formWrap.hidden = false;
        alreadyWrap.hidden = true;
      }
    } else {
      reportCard.hidden = true;
    }
  }

  async function loadExistingCustomerSession() {
    try {
      const res = await fetch("/api/public/session", {
        method: "GET",
        credentials: "same-origin",
      });
      if (res.ok) {
        const data = await res.json();
        document.getElementById("lookup-card").hidden = true;
        renderVerificationResult(data);
        return true;
      }
    } catch {
      // Ignore missing session
    }
    return false;
  }

  async function loadReasons() {
    const res = await TrustAPI.request("/api/public/reasons");
    const selectEl = document.getElementById("report-reason");
    selectEl.innerHTML = (res.reasons || [])
      .map((r) => `<option value="${TrustAPI.escapeHtml(r)}">${TrustAPI.escapeHtml(r)}</option>`)
      .join("");
  }

  document.addEventListener("DOMContentLoaded", async () => {
    await loadReasons();

    const params = new URLSearchParams(window.location.search);
    const prefilled = params.get("id");
    if (prefilled) {
      document.getElementById("trust-id-input").value = prefilled;
    }

    await loadExistingCustomerSession();

    const toggleBtn = document.getElementById("toggle-report-form-btn");
    const reportForm = document.getElementById("suspicious-report-form");
    toggleBtn.addEventListener("click", () => {
      reportForm.hidden = !reportForm.hidden;
    });

    document.getElementById("verify-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("trust-id-input");
      const trustId = input.value.trim();
      const btn = document.getElementById("verify-submit-btn");
      btn.disabled = true;
      btn.textContent = "Verifying...";

      try {
        const res = await fetch("/api/public/verify", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ trust_id: trustId }),
        });
        const data = await res.json();
        if (data && data.overall_status) {
          if (res.ok) {
            document.getElementById("lookup-card").hidden = true;
            TrustAPI.showToast("Trust ID verified and redeemed.", "success");
          } else {
            TrustAPI.showToast(data.overall_status + ": " + data.status_explanation, "error");
          }
          renderVerificationResult(data);
        } else {
          TrustAPI.showToast(data.detail || "Unable to verify Trust ID.", "error");
        }
      } catch (err) {
        TrustAPI.showToast(err.message, "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "Verify Communication";
      }
    });

    reportForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = document.getElementById("report-error");
      errEl.hidden = true;
      const btn = document.getElementById("report-submit-btn");
      btn.disabled = true;

      const payload = {
        reason: document.getElementById("report-reason").value,
        description: document.getElementById("report-description").value.trim() || null,
      };

      try {
        await TrustAPI.request("/api/public/report-suspicious", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        TrustAPI.showToast("Suspicious activity report submitted.", "success");
        await loadExistingCustomerSession();
      } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
      } finally {
        btn.disabled = false;
      }
    });
  });
})();
