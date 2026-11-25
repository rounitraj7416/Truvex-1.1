/**
 * Company Admin Dashboard controller.
 */

(() => {
  let supportedPurposes = [];
  let employeesCache = [];
  let currentCompany = null;

  function renderCompanyBanner(company) {
    const banner = document.getElementById("company-status-banner");
    const addBtn = document.getElementById("open-add-employee-btn");
    const status = company.verification_status;

    document.getElementById("company-name-title").textContent = company.company_name;
    document.getElementById("company-meta").textContent = `${company.industry} • Reg #${company.registration_number} • ${company.business_email}`;
    document.getElementById("company-status-badge").innerHTML = TrustAPI.statusBadge(status);

    if (status === "VERIFIED") {
      banner.className = "alert alert-success";
      banner.innerHTML =
        "<strong>Verified Company:</strong> Your organization is approved. You can register employees, assign communication purposes, and authorize Trust ID generation.";
      addBtn.disabled = false;
    } else if (status === "PENDING") {
      banner.className = "alert alert-warning";
      banner.innerHTML =
        "<strong>Pending Platform Approval:</strong> Your registration is under review by a platform administrator. Adding active authorized employees and issuing Trust IDs are blocked until verified.";
      addBtn.disabled = true;
    } else if (status === "SUSPENDED") {
      banner.className = "alert alert-danger";
      banner.innerHTML = `<strong>Company Suspended:</strong> ${TrustAPI.escapeHtml(
        company.rejection_reason || "Contact platform administration."
      )} Employee registration and Trust ID issuance are disabled.`;
      addBtn.disabled = true;
    } else {
      banner.className = "alert alert-danger";
      banner.innerHTML = `<strong>Registration Rejected:</strong> ${TrustAPI.escapeHtml(
        company.rejection_reason || "See administrator notes."
      )}`;
      addBtn.disabled = true;
    }
  }

  function renderHistory(history) {
    const container = document.getElementById("company-history-list");
    if (!history || history.length === 0) {
      container.innerHTML = `<div class="empty-state">No status history recorded yet.</div>`;
      return;
    }
    container.innerHTML = history
      .map(
        (h) => `
        <div class="kv-row">
          <div>
            <strong>${TrustAPI.escapeHtml(h.action)}</strong>
            <div class="form-hint">${TrustAPI.escapeHtml(h.actor_role)}${
          h.metadata && (h.metadata.reason || h.metadata.note)
            ? " — " + TrustAPI.escapeHtml(h.metadata.reason || h.metadata.note)
            : ""
        }</div>
          </div>
          <div class="form-hint">${TrustAPI.formatDateTime(h.timestamp)}</div>
        </div>`
      )
      .join("");
  }

  function renderEmployees(employees) {
    employeesCache = employees;
    const tbody = document.getElementById("employees-tbody");
    const totalEl = document.getElementById("stat-employees");
    const voiceEl = document.getElementById("stat-voice-enrolled");
    const enrolledCount = employees.filter((e) => e.voice_enrolled).length;
    if (typeof TrustMotion !== "undefined" && TrustMotion.animateStatValue) {
      TrustMotion.animateStatValue(totalEl, employees.length);
      TrustMotion.animateStatValue(voiceEl, enrolledCount);
    } else {
      totalEl.textContent = employees.length;
      voiceEl.textContent = enrolledCount;
    }

    if (!employees.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No employees registered yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = employees
      .map((emp) => {
        const purposesHtml = (emp.allowed_purposes || [])
          .map((p) => `<span class="badge badge-blue" style="margin:2px;">${TrustAPI.escapeHtml(p)}</span>`)
          .join(" ");
        const voiceHtml = emp.voice_enrolled
          ? `${TrustAPI.statusBadge("ENROLLED")} ${
              emp.latest_enrollment && emp.latest_enrollment.is_mock
                ? '<span class="badge badge-amber" title="Mock Provider">DEMO</span>'
                : ""
            }`
          : TrustAPI.statusBadge("PENDING");
        const activeHtml = emp.is_active
          ? TrustAPI.statusBadge("ACTIVE")
          : TrustAPI.statusBadge("REVOKED");

        return `
          <tr>
            <td>
              <strong>${TrustAPI.escapeHtml(emp.full_name)}</strong>
              <div class="form-hint mono">${TrustAPI.escapeHtml(emp.employee_code)}</div>
              <div class="form-hint">${TrustAPI.escapeHtml(emp.email)}</div>
            </td>
            <td>
              <div>${TrustAPI.escapeHtml(emp.designation)}</div>
              <div class="form-hint">${TrustAPI.escapeHtml(emp.department)} • ${TrustAPI.escapeHtml(
          emp.assigned_role
        )}</div>
            </td>
            <td>${purposesHtml}</td>
            <td>${voiceHtml}</td>
            <td>${activeHtml}</td>
            <td>
              <div style="display:flex;gap:0.35rem;flex-wrap:wrap;">
                <button class="btn btn-secondary btn-sm" data-edit-emp="${emp.id}">Edit</button>
                <button class="btn ${emp.is_active ? "btn-danger" : "btn-success"} btn-sm" data-toggle-emp="${
          emp.id
        }" data-active="${emp.is_active}">
                  ${emp.is_active ? "Deactivate" : "Reactivate"}
                </button>
              </div>
            </td>
          </tr>
        `;
      })
      .join("");

    tbody.querySelectorAll("[data-edit-emp]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = Number(btn.getAttribute("data-edit-emp"));
        const emp = employeesCache.find((e) => e.id === id);
        if (emp) openEditModal(emp);
      });
    });

    tbody.querySelectorAll("[data-toggle-emp]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = Number(btn.getAttribute("data-toggle-emp"));
        const currentlyActive = btn.getAttribute("data-active") === "true";
        btn.disabled = true;
        try {
          await TrustAPI.request(`/api/employees/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: !currentlyActive }),
          });
          TrustAPI.showToast(
            !currentlyActive ? "Employee reactivated." : "Employee deactivated.",
            "success"
          );
          await refreshDashboard();
        } catch (err) {
          TrustAPI.showToast(err.message, "error");
          btn.disabled = false;
        }
      });
    });
  }

  function renderSessions(sessions) {
    const tbody = document.getElementById("company-sessions-tbody");
    document.getElementById("stat-sessions").textContent = sessions.length;

    if (!sessions.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No Trust ID sessions issued by your employees yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = sessions
      .map(
        (s) => `
        <tr>
          <td>
            <strong>${TrustAPI.escapeHtml(s.employee_name)}</strong>
            <div class="form-hint mono">${TrustAPI.escapeHtml(s.employee_code)}</div>
          </td>
          <td>${TrustAPI.escapeHtml(s.purpose)}</td>
          <td>${TrustAPI.statusBadge(s.status)}</td>
          <td>
            <div class="form-hint">Issued: ${TrustAPI.formatDateTime(s.issued_at)}</div>
            <div class="form-hint">Expires: ${TrustAPI.formatDateTime(s.expires_at)}</div>
          </td>
          <td>${
            s.suspicious_report_count > 0
              ? `<span class="badge badge-red">${s.suspicious_report_count} Flag(s)</span>`
              : '<span class="badge badge-slate">None</span>'
          }</td>
          <td>
            ${
              s.status === "ACTIVE"
                ? `<button class="btn btn-danger btn-sm" data-revoke-session="${s.id}">Revoke</button>`
                : "—"
            }
          </td>
        </tr>
      `
      )
      .join("");

    tbody.querySelectorAll("[data-revoke-session]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sid = Number(btn.getAttribute("data-revoke-session"));
        btn.disabled = true;
        try {
          await TrustAPI.request(`/api/companies/me/sessions/${sid}/revoke`, {
            method: "POST",
          });
          TrustAPI.showToast("Session revoked.", "success");
          await refreshDashboard();
        } catch (err) {
          TrustAPI.showToast(err.message, "error");
          btn.disabled = false;
        }
      });
    });
  }

  function populatePurposeCheckboxes(containerId, selected = []) {
    const el = document.getElementById(containerId);
    el.innerHTML = supportedPurposes
      .map(
        (purpose) => `
        <label class="checkbox-item">
          <input type="checkbox" value="${TrustAPI.escapeHtml(purpose)}" ${
          selected.includes(purpose) ? "checked" : ""
        } />
          <span>${TrustAPI.escapeHtml(purpose)}</span>
        </label>
      `
      )
      .join("");
  }

  function getSelectedPurposes(containerId) {
    return Array.from(
      document.querySelectorAll(`#${containerId} input[type="checkbox"]:checked`)
    ).map((cb) => cb.value);
  }

  function openAddModal() {
    document.getElementById("add-employee-form").reset();
    document.getElementById("add-employee-error").hidden = true;
    populatePurposeCheckboxes("add-purposes-grid", ["Account verification"]);
    document.getElementById("add-employee-modal").classList.add("open");
  }

  function openEditModal(emp) {
    document.getElementById("edit-emp-id").value = emp.id;
    document.getElementById("edit-emp-name").textContent = `${emp.full_name} (${emp.employee_code})`;
    document.getElementById("edit-designation").value = emp.designation;
    document.getElementById("edit-department").value = emp.department;
    document.getElementById("edit-assigned-role").value = emp.assigned_role;
    document.getElementById("edit-employee-error").hidden = true;
    populatePurposeCheckboxes("edit-purposes-grid", emp.allowed_purposes || []);
    document.getElementById("edit-employee-modal").classList.add("open");
  }

  async function refreshDashboard() {
    const [companyData, employees, sessionsData] = await Promise.all([
      TrustAPI.request("/api/companies/me"),
      TrustAPI.request("/api/employees"),
      TrustAPI.request("/api/companies/me/sessions"),
    ]);
    currentCompany = companyData.company;
    renderCompanyBanner(currentCompany);
    renderHistory(companyData.history);
    renderEmployees(employees);
    renderSessions(sessionsData.sessions || []);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const user = await TrustAuth.requireAuth(["company_admin"]);
    if (!user) return;
    document.getElementById("nav-user-label").textContent = user.full_name;

    const purposeRes = await TrustAPI.request("/api/employees/purposes");
    supportedPurposes = purposeRes.purposes || [];

    await refreshDashboard();

    document.getElementById("open-add-employee-btn").addEventListener("click", openAddModal);
    document.querySelectorAll("[data-close-modal]").forEach((btn) => {
      btn.addEventListener("click", () => {
        btn.closest(".modal-backdrop").classList.remove("open");
      });
    });

    document.getElementById("add-employee-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = document.getElementById("add-employee-error");
      errEl.hidden = true;
      const submitBtn = document.getElementById("add-employee-submit");
      submitBtn.disabled = true;

      const purposes = getSelectedPurposes("add-purposes-grid");
      if (!purposes.length) {
        errEl.textContent = "Select at least one allowed communication purpose.";
        errEl.hidden = false;
        submitBtn.disabled = false;
        return;
      }

      const payload = {
        full_name: document.getElementById("emp-full-name").value.trim(),
        email: document.getElementById("emp-email").value.trim(),
        employee_code: document.getElementById("emp-code").value.trim(),
        designation: document.getElementById("emp-designation").value.trim(),
        department: document.getElementById("emp-department").value.trim(),
        assigned_role: document.getElementById("emp-role").value.trim(),
        allowed_purposes: purposes,
        password: document.getElementById("emp-password").value,
      };

      try {
        await TrustAPI.request("/api/employees", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        document.getElementById("add-employee-modal").classList.remove("open");
        TrustAPI.showToast("Employee added successfully.", "success");
        await refreshDashboard();
      } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
      } finally {
        submitBtn.disabled = false;
      }
    });

    document.getElementById("edit-employee-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = document.getElementById("edit-employee-error");
      errEl.hidden = true;
      const id = document.getElementById("edit-emp-id").value;
      const purposes = getSelectedPurposes("edit-purposes-grid");
      if (!purposes.length) {
        errEl.textContent = "Select at least one allowed communication purpose.";
        errEl.hidden = false;
        return;
      }

      try {
        await TrustAPI.request(`/api/employees/${id}`, {
          method: "PATCH",
          body: JSON.stringify({
            designation: document.getElementById("edit-designation").value.trim(),
            department: document.getElementById("edit-department").value.trim(),
            assigned_role: document.getElementById("edit-assigned-role").value.trim(),
            allowed_purposes: purposes,
          }),
        });
        document.getElementById("edit-employee-modal").classList.remove("open");
        TrustAPI.showToast("Employee permissions updated.", "success");
        await refreshDashboard();
      } catch (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
      }
    });
  });
})();
