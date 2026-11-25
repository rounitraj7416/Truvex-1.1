/**
 * Platform Administrator Console controller.
 */

(() => {
  let companyStatusFilter = "";

  function setStat(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    if (typeof TrustMotion !== "undefined" && TrustMotion.animateStatValue) {
      TrustMotion.animateStatValue(el, value);
    } else {
      el.textContent = value;
    }
  }

  async function loadStats() {
    const s = await TrustAPI.request("/api/admin/stats");
    setStat("stat-total-companies", s.total_companies);
    setStat("stat-pending-companies", s.pending_companies);
    setStat("stat-verified-companies", s.verified_companies);
    setStat("stat-total-employees", s.total_employees);
    setStat("stat-issued-ids", s.issued_trust_ids);
    setStat("stat-active-sessions", s.active_sessions);
    setStat("stat-expired-sessions", s.expired_sessions);
    setStat("stat-suspicious-reports", s.suspicious_reports);
  }

  async function loadCompanies() {
    const qs = companyStatusFilter ? `?status=${encodeURIComponent(companyStatusFilter)}` : "";
    const companies = await TrustAPI.request(`/api/admin/companies${qs}`);
    const tbody = document.getElementById("admin-companies-tbody");

    if (!companies.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No companies match this filter.</td></tr>`;
      return;
    }

    tbody.innerHTML = companies
      .map((c) => {
        const actions = [];
        if (c.verification_status === "PENDING" || c.verification_status === "REJECTED") {
          actions.push(
            `<button class="btn btn-success btn-sm" data-company-action="approve" data-id="${c.id}">Approve</button>`
          );
        }
        if (c.verification_status === "PENDING") {
          actions.push(
            `<button class="btn btn-danger btn-sm" data-company-action="reject" data-id="${c.id}">Reject</button>`
          );
        }
        if (c.verification_status === "VERIFIED") {
          actions.push(
            `<button class="btn btn-danger btn-sm" data-company-action="suspend" data-id="${c.id}">Suspend</button>`
          );
        }
        if (c.verification_status === "SUSPENDED") {
          actions.push(
            `<button class="btn btn-success btn-sm" data-company-action="reactivate" data-id="${c.id}">Reactivate</button>`
          );
        }
        actions.push(
          `<button class="btn btn-secondary btn-sm" data-company-history="${c.id}">History</button>`
        );

        return `
          <tr>
            <td>
              <strong>${TrustAPI.escapeHtml(c.company_name)}</strong>
              <div class="form-hint">${TrustAPI.escapeHtml(c.business_email)} • ${TrustAPI.escapeHtml(
          c.phone
        )}</div>
            </td>
            <td>${TrustAPI.escapeHtml(c.industry)}</td>
            <td class="mono">${TrustAPI.escapeHtml(c.registration_number)}</td>
            <td>
              ${TrustAPI.statusBadge(c.verification_status)}
              ${
                c.rejection_reason
                  ? `<div class="form-hint">${TrustAPI.escapeHtml(c.rejection_reason)}</div>`
                  : ""
              }
            </td>
            <td class="form-hint">${TrustAPI.formatDateTime(c.created_at)}</td>
            <td style="display:flex;gap:0.35rem;flex-wrap:wrap;">${actions.join("")}</td>
          </tr>
        `;
      })
      .join("");

    tbody.querySelectorAll("[data-company-action]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const action = btn.getAttribute("data-company-action");
        if (action === "reject") {
          openReasonModal(id, "reject", "Reject Company Registration");
          return;
        }
        if (action === "suspend") {
          openReasonModal(id, "suspend", "Suspend Approved Company");
          return;
        }
        btn.disabled = true;
        try {
          await TrustAPI.request(`/api/admin/companies/${id}/${action}`, {
            method: "POST",
            body: JSON.stringify({}),
          });
          TrustAPI.showToast(`Company ${action}d.`, "success");
          await refreshAll();
        } catch (err) {
          TrustAPI.showToast(err.message, "error");
          btn.disabled = false;
        }
      });
    });

    tbody.querySelectorAll("[data-company-history]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-company-history");
        showCompanyHistory(id);
      });
    });
  }

  function openReasonModal(companyId, action, title) {
    document.getElementById("reason-modal-title").textContent = title;
    document.getElementById("reason-company-id").value = companyId;
    document.getElementById("reason-action").value = action;
    document.getElementById("reason-input").value = "";
    document.getElementById("reason-modal").classList.add("open");
  }

  async function showCompanyHistory(companyId) {
    const data = await TrustAPI.request(`/api/admin/companies/${companyId}/history`);
    document.getElementById("history-modal-title").textContent = `${data.company.company_name} — History`;
    const body = document.getElementById("history-modal-body");
    body.innerHTML =
      (data.history || [])
        .map(
          (h) => `
        <div class="kv-row">
          <div>
            <strong>${TrustAPI.escapeHtml(h.action)}</strong>
            <div class="form-hint">${TrustAPI.escapeHtml(h.actor_role)} • ${TrustAPI.escapeHtml(
            JSON.stringify(h.metadata || {})
          )}</div>
          </div>
          <div class="form-hint">${TrustAPI.formatDateTime(h.timestamp)}</div>
        </div>`
        )
        .join("") || '<div class="empty-state">No history entries.</div>';
    document.getElementById("history-modal").classList.add("open");
  }

  async function loadEmployees() {
    const res = await TrustAPI.request("/api/admin/employees");
    const list = res.employees || [];
    const tbody = document.getElementById("admin-employees-tbody");
    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No employees registered yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = list
      .map(
        (e) => `
      <tr>
        <td><strong>${TrustAPI.escapeHtml(e.full_name)}</strong><div class="form-hint">${TrustAPI.escapeHtml(e.email)}</div></td>
        <td>${TrustAPI.escapeHtml(e.company_name)} ${TrustAPI.statusBadge(e.company_status)}</td>
        <td class="mono">${TrustAPI.escapeHtml(e.employee_code)}</td>
        <td>${TrustAPI.escapeHtml(e.designation)} (${TrustAPI.escapeHtml(e.department)})</td>
        <td>${e.voice_enrolled ? TrustAPI.statusBadge("ENROLLED") : TrustAPI.statusBadge("PENDING")}</td>
        <td>${e.is_active ? TrustAPI.statusBadge("ACTIVE") : TrustAPI.statusBadge("REVOKED")}</td>
      </tr>`
      )
      .join("");
  }

  async function loadSessions() {
    const list = await TrustAPI.request("/api/admin/sessions");
    const tbody = document.getElementById("admin-sessions-tbody");
    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No Trust ID sessions recorded.</td></tr>`;
      return;
    }
    tbody.innerHTML = list
      .map(
        (s) => `
      <tr>
        <td>${TrustAPI.escapeHtml(s.company_name)}</td>
        <td>${TrustAPI.escapeHtml(s.employee_name)} <span class="form-hint mono">(${TrustAPI.escapeHtml(
          s.employee_code
        )})</span></td>
        <td>${TrustAPI.escapeHtml(s.purpose)}</td>
        <td>${TrustAPI.statusBadge(s.status)}</td>
        <td class="mono">${TrustAPI.escapeHtml(s.ai_provider)} ${
          s.is_mock ? '<span class="badge badge-amber">MOCK</span>' : ""
        }</td>
        <td class="form-hint">${TrustAPI.formatDateTime(s.issued_at)}</td>
        <td>
          ${
            s.status === "ACTIVE"
              ? `<button class="btn btn-danger btn-sm" data-admin-revoke="${s.id}">Revoke</button>`
              : s.suspicious_report_count > 0
              ? `<span class="badge badge-red">${s.suspicious_report_count} Report</span>`
              : "—"
          }
        </td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("[data-admin-revoke]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sid = btn.getAttribute("data-admin-revoke");
        btn.disabled = true;
        try {
          await TrustAPI.request(`/api/admin/sessions/${sid}/revoke`, { method: "POST" });
          TrustAPI.showToast("Session revoked.", "success");
          await refreshAll();
        } catch (err) {
          TrustAPI.showToast(err.message, "error");
          btn.disabled = false;
        }
      });
    });
  }

  async function loadReports() {
    const list = await TrustAPI.request("/api/admin/reports");
    const tbody = document.getElementById("admin-reports-tbody");
    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No suspicious reports submitted.</td></tr>`;
      return;
    }
    tbody.innerHTML = list
      .map(
        (r) => `
      <tr>
        <td><strong>${TrustAPI.escapeHtml(r.company_name)}</strong><div class="form-hint">${TrustAPI.escapeHtml(
          r.employee_name
        )}</div></td>
        <td>${TrustAPI.escapeHtml(r.purpose)}</td>
        <td><strong>${TrustAPI.escapeHtml(r.reason)}</strong>${
          r.description ? `<div class="form-hint">${TrustAPI.escapeHtml(r.description)}</div>` : ""
        }</td>
        <td>${TrustAPI.statusBadge(r.status)}</td>
        <td class="form-hint">${TrustAPI.formatDateTime(r.created_at)}</td>
        <td>
          <select class="form-control" data-report-status="${r.id}" style="min-width:160px;">
            ${["OPEN", "REVIEWED", "CONFIRMED_SUSPICIOUS", "DISMISSED"]
              .map(
                (st) =>
                  `<option value="${st}" ${r.status === st ? "selected" : ""}>${st}</option>`
              )
              .join("")}
          </select>
        </td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("[data-report-status]").forEach((sel) => {
      sel.addEventListener("change", async () => {
        const rid = sel.getAttribute("data-report-status");
        try {
          await TrustAPI.request(`/api/admin/reports/${rid}`, {
            method: "PATCH",
            body: JSON.stringify({ status: sel.value }),
          });
          TrustAPI.showToast("Report status updated.", "success");
          await loadReports();
        } catch (err) {
          TrustAPI.showToast(err.message, "error");
        }
      });
    });
  }

  async function loadAuditLogs() {
    const logs = await TrustAPI.request("/api/admin/audit-logs?limit=100");
    const tbody = document.getElementById("admin-audit-tbody");
    if (!logs.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No audit logs recorded.</td></tr>`;
      return;
    }
    tbody.innerHTML = logs
      .map(
        (l) => `
      <tr>
        <td class="form-hint">${TrustAPI.formatDateTime(l.timestamp)}</td>
        <td><strong>${TrustAPI.escapeHtml(l.action)}</strong></td>
        <td>${TrustAPI.escapeHtml(l.actor_role)}${
          l.actor_id ? ` (#${l.actor_id})` : ""
        }</td>
        <td class="mono">${TrustAPI.escapeHtml(l.entity_type)}${
          l.entity_id ? `:${l.entity_id}` : ""
        }</td>
        <td class="form-hint mono">${TrustAPI.escapeHtml(JSON.stringify(l.metadata || {}))}</td>
      </tr>`
      )
      .join("");
  }

  async function refreshAll() {
    await Promise.all([
      loadStats(),
      loadCompanies(),
      loadEmployees(),
      loadSessions(),
      loadReports(),
      loadAuditLogs(),
    ]);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const user = await TrustAuth.requireAuth(["platform_admin"]);
    if (!user) return;
    document.getElementById("nav-user-label").textContent = user.full_name;

    // Tabs
    document.querySelectorAll("[data-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.getAttribute("data-tab");
        document.querySelectorAll("[data-tab]").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        document.querySelectorAll("[data-tab-panel]").forEach((p) => {
          const isMatch = p.getAttribute("data-tab-panel") === target;
          p.hidden = !isMatch;
          p.classList.remove("tab-panel-animate");
          if (isMatch) {
            void p.offsetWidth;
            p.classList.add("tab-panel-animate");
          }
        });
      });
    });

    document.getElementById("company-status-filter").addEventListener("change", (e) => {
      companyStatusFilter = e.target.value;
      loadCompanies();
    });

    document.querySelectorAll("[data-close-modal]").forEach((btn) => {
      btn.addEventListener("click", () => {
        btn.closest(".modal-backdrop").classList.remove("open");
      });
    });

    document.getElementById("reason-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const id = document.getElementById("reason-company-id").value;
      const action = document.getElementById("reason-action").value;
      const reason = document.getElementById("reason-input").value.trim();
      try {
        await TrustAPI.request(`/api/admin/companies/${id}/${action}`, {
          method: "POST",
          body: JSON.stringify({ reason }),
        });
        document.getElementById("reason-modal").classList.remove("open");
        TrustAPI.showToast(`Company ${action}ed.`, "success");
        await refreshAll();
      } catch (err) {
        TrustAPI.showToast(err.message, "error");
      }
    });

    await refreshAll();
  });
})();
