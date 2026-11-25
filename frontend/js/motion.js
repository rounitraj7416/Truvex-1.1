/**
 * The Trust Layer — Scroll-Choreographed Five-Gate Clearinghouse & Live TTL Specimen
 * Native scroll-driven progress (no scroll-jacking), 60fps compositor transforms,
 * and static-complete fallback under prefers-reduced-motion.
 */

const TrustMotion = (() => {
  const GATES = [
    {
      code: "01 / 05",
      title: "Business verification gate",
      desc: "Before an employee can initiate verification, Layer 1 checks that their company exists in SQLite and holds an explicit platform-administrator VERIFIED status.",
      spec: "services/business_verification.py -> Company.verification_status == 'VERIFIED'",
    },
    {
      code: "02 / 05",
      title: "Employee identity & attestation",
      desc: "Layer 2 confirms the caller holds an active employee account bound to that exact company, carries COMPANY_ATTESTED status, and has completed voice enrollment.",
      spec: "services/employee_verification.py -> user.is_active && employee.voice_enrolled",
    },
    {
      code: "03 / 05",
      title: "Isolated AI voice & deepfake check",
      desc: "Layer 3 routes a fresh MediaRecorder audio sample through an isolated provider interface to check speaker match and synthetic speech signals without storing raw audio.",
      spec: "trust_engine/factory.py -> verify_voice() && detect_deepfake()",
    },
    {
      code: "04 / 05",
      title: "Purpose mandate enforcement",
      desc: "Layer 4 refuses arbitrary free-text call reasons. The selected purpose—such as Fraud alert or Loan verification—must match the employee's assigned permissions.",
      spec: "services/permission_verification.py -> purpose in employee.allowed_purposes",
    },
    {
      code: "05 / 05",
      title: "Atomic single-use Trust ID minted",
      desc: "Only when Gates 01–04 lock does Layer 5 mint a 5-minute cryptographically random Trust ID, store its SHA-256 hash, and enforce single-use SQLite redemption.",
      spec: "services/session_service.py -> UPDATE ... WHERE status='ACTIVE' AND expires_at > now",
    },
  ];

  const prefersReducedMotion = () =>
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function initHeroCountdown() {
    const el = document.getElementById("hero-ttl-countdown");
    if (!el) return;
    if (prefersReducedMotion()) {
      el.textContent = "05:00 remaining";
      return;
    }

    let secondsLeft = 300;
    const render = () => {
      const m = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
      const s = String(secondsLeft % 60).padStart(2, "0");
      el.textContent = `${m}:${s} remaining`;
    };
    render();

    setInterval(() => {
      secondsLeft = secondsLeft > 1 ? secondsLeft - 1 : 300;
      render();
    }, 1000);
  }

  function initClearinghouseChoreography() {
    const track = document.getElementById("clearinghouse-track");
    if (!track) return;

    const counterEl = document.getElementById("gate-counter");
    const titleEl = document.getElementById("gate-active-title");
    const descEl = document.getElementById("gate-active-desc");
    const specEl = document.getElementById("gate-active-spec");
    const railFill = document.getElementById("gate-rail-fill");
    const sealFooter = document.getElementById("gate-seal-footer");
    const sealText = document.getElementById("gate-seal-status");
    const units = Array.from(track.querySelectorAll(".gate-unit"));

    let lastGateIndex = -1;
    let ticking = false;

    function applyGate(activeIdx, progressRatio) {
      if (railFill) {
        railFill.style.transform = `scaleX(${Math.max(0.2, Math.min(1, progressRatio)).toFixed(4)})`;
      }

      if (activeIdx === lastGateIndex) return;
      lastGateIndex = activeIdx;

      const gate = GATES[activeIdx] || GATES[0];
      if (counterEl) counterEl.textContent = `Gate ${gate.code}`;
      if (titleEl) titleEl.textContent = gate.title;
      if (descEl) descEl.textContent = gate.desc;
      if (specEl) specEl.textContent = gate.spec;

      const allLocked = activeIdx >= GATES.length - 1;
      units.forEach((unit, idx) => {
        const pill = unit.querySelector(".gate-state-pill");
        const locked = idx < activeIdx || (allLocked && idx === activeIdx);
        const current = idx === activeIdx;

        unit.classList.toggle("is-locked", locked);
        unit.classList.toggle("is-current", current);
        if (pill) {
          pill.textContent = locked ? "LOCKED" : current ? "CHECKING" : "QUEUED";
        }
      });

      if (sealFooter && sealText) {
        sealFooter.classList.toggle("is-minted", allLocked);
        sealText.textContent = allLocked
          ? "Seal locked -> TL-7K4M-9P2Q-3V8X-5N1R"
          : "Seal pending all 5 gates";
      }
    }

    // Allow clicking any gate unit directly (useful on mobile or quick inspection)
    units.forEach((unit, idx) => {
      unit.style.cursor = "pointer";
      unit.addEventListener("click", () => {
        applyGate(idx, (idx + 1) / GATES.length);
      });
    });

    if (prefersReducedMotion()) {
      applyGate(4, 1);
      return;
    }

    function updateFromScroll() {
      ticking = false;
      const isCompact = window.innerWidth <= 900;
      if (isCompact) {
        // On mobile where sticky track collapses, keep the final overview legible or let clicks switch
        if (lastGateIndex === -1) applyGate(4, 1);
        return;
      }

      const rect = track.getBoundingClientRect();
      const scrollable = Math.max(track.offsetHeight - window.innerHeight, 1);
      const scrolled = Math.min(Math.max(-rect.top, 0), scrollable);
      const ratio = scrolled / scrollable;
      const idx = Math.min(GATES.length - 1, Math.floor(ratio * GATES.length));
      applyGate(idx, 0.2 + ratio * 0.8);
    }

    function onScroll() {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(updateFromScroll);
      }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    updateFromScroll();
  }

  function animateStatValue(el, newValue) {
    if (!el) return;
    const target = Number(newValue);
    if (!Number.isFinite(target) || prefersReducedMotion()) {
      el.textContent = newValue;
      return;
    }

    const duration = 380;
    const startTime = performance.now();
    function step(now) {
      const p = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = String(Math.round(target * eased));
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = String(target);
    }
    requestAnimationFrame(step);
  }

  document.addEventListener("DOMContentLoaded", () => {
    initHeroCountdown();
    initClearinghouseChoreography();
  });

  return {
    animateStatValue,
    prefersReducedMotion,
  };
})();
