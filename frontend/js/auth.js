/**
 * Authentication helpers, role routing, and session guards.
 */

const TrustAuth = (() => {
  function roleHome(role) {
    if (role === "platform_admin") return "/admin-dashboard.html";
    if (role === "company_admin") return "/company-dashboard.html";
    if (role === "employee") return "/employee-dashboard.html";
    return "/";
  }

  async function getCurrentUser() {
    try {
      return await TrustAPI.request("/api/auth/me", { method: "GET" });
    } catch {
      return null;
    }
  }

  async function requireAuth(allowedRoles) {
    const user = await getCurrentUser();
    if (!user) {
      window.location.href = "/login.html";
      return null;
    }
    if (allowedRoles && !allowedRoles.includes(user.role)) {
      TrustAPI.showToast("Redirecting to your authorized workspace.", "info");
      window.location.href = roleHome(user.role);
      return null;
    }
    return user;
  }

  async function logout() {
    try {
      await TrustAPI.request("/api/auth/logout", { method: "POST" });
    } finally {
      window.location.href = "/login.html";
    }
  }

  function bindLogoutButtons() {
    document.querySelectorAll("[data-logout]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        logout();
      });
    });
  }

  // Handle login page if present
  function initLoginPage() {
    const form = document.getElementById("login-form");
    if (!form) return;

    const errBox = document.getElementById("login-error");
    const submitBtn = document.getElementById("login-submit");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errBox.hidden = true;
      submitBtn.disabled = true;
      submitBtn.textContent = "Signing in...";

      const email = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value;

      try {
        const data = await TrustAPI.request("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        TrustAPI.showToast("Signed in successfully.", "success");
        window.location.href = roleHome(data.user.role);
      } catch (err) {
        errBox.textContent = err.message;
        errBox.hidden = false;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Sign In";
      }
    });
  }

  // Handle company registration page if present
  function initCompanyRegisterPage() {
    const form = document.getElementById("company-register-form");
    if (!form) return;

    const errBox = document.getElementById("register-error");
    const submitBtn = document.getElementById("register-submit");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errBox.hidden = true;
      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting registration...";

      const payload = {
        company_name: document.getElementById("company-name").value.trim(),
        business_email: document.getElementById("business-email").value.trim(),
        phone: document.getElementById("company-phone").value.trim(),
        industry: document.getElementById("company-industry").value.trim(),
        registration_number: document.getElementById("registration-number").value.trim(),
        admin_full_name: document.getElementById("admin-full-name").value.trim() || null,
        password: document.getElementById("company-password").value,
      };

      try {
        await TrustAPI.request("/api/companies/register", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        TrustAPI.showToast("Company registered. Status is PENDING admin approval.", "success");
        window.location.href = "/company-dashboard.html";
      } catch (err) {
        errBox.textContent = err.message;
        errBox.hidden = false;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Register Company";
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindLogoutButtons();
    initLoginPage();
    initCompanyRegisterPage();
  });

  return {
    roleHome,
    getCurrentUser,
    requireAuth,
    logout,
  };
})();
