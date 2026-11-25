/**
 * Shared API client, HTML escaping, date formatting, and toast utilities.
 */

const TrustAPI = (() => {
  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatDateTime(isoString) {
    if (!isoString) return "—";
    const dt = new Date(isoString);
    if (Number.isNaN(dt.getTime())) return String(isoString);
    return dt.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function statusBadge(status) {
    const s = String(status || "").toUpperCase();
    let cls = "badge-slate";
    if (
      ["VERIFIED", "ACTIVE", "ENROLLED", "MATCH", "AUTHENTIC", "ISSUED", "COMPANY_ATTESTED"].includes(s)
    ) {
      cls = "badge-green";
    } else if (["PENDING", "REDEEMED", "REVIEWED"].includes(s)) {
      cls = "badge-amber";
    } else if (
      ["REJECTED", "SUSPENDED", "REVOKED", "FAILED", "SUSPICIOUS", "NO_MATCH", "DEEPFAKE_SUSPECTED", "INVALID", "EXPIRED", "OPEN", "CONFIRMED_SUSPICIOUS"].includes(s)
    ) {
      cls = "badge-red";
    } else if (["DISMISSED"].includes(s)) {
      cls = "badge-blue";
    }
    return `<span class="badge ${cls}">${escapeHtml(status)}</span>`;
  }

  function ensureToastContainer() {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "toast-container";
      container.setAttribute("aria-live", "polite");
      document.body.appendChild(container);
    }
    return container;
  }

  function showToast(message, type = "info") {
    const container = ensureToastContainer();
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => {
      toast.classList.add("toast-visible");
    });
    setTimeout(() => {
      toast.classList.add("toast-leaving");
      setTimeout(() => toast.remove(), 260);
    }, 3900);
  }

  async function request(url, options = {}) {
    const fetchOpts = {
      credentials: "same-origin",
      ...options,
      headers: {
        ...(options.headers || {}),
      },
    };
    if (
      fetchOpts.body &&
      !(fetchOpts.body instanceof FormData) &&
      !fetchOpts.headers["Content-Type"]
    ) {
      fetchOpts.headers["Content-Type"] = "application/json";
    }

    const res = await fetch(url, fetchOpts);
    const contentType = res.headers.get("content-type") || "";
    let data = null;
    if (contentType.includes("application/json")) {
      data = await res.json();
    } else {
      data = await res.text();
    }

    if (!res.ok) {
      const errMsg =
        (data && (data.detail || data.message || data.status_explanation)) ||
        `Request failed (${res.status})`;
      const error = new Error(
        typeof errMsg === "string" ? errMsg : JSON.stringify(errMsg)
      );
      error.status = res.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  async function getHealth() {
    return request("/api/health", { method: "GET" });
  }

  return {
    escapeHtml,
    formatDateTime,
    statusBadge,
    showToast,
    request,
    getHealth,
  };
})();
