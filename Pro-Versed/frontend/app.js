/**
 * PRO-VERSED — National Student Innovation Platform & Project Showcase
 * Core Application Engine, Authentication & Security Controller, AI Assistant & IPFS
 */

// ==========================================
// GLOBAL STATE & CONFIGURATION
// ==========================================
const state = {
  currentUser: null,
  isAuthenticated: false,
  sessionToken: null,
  sessionInfo: null,
  lockoutTimerInterval: null,
  activeTab: "dashboard",
  projects: [],
  selectedProject: null,
  tasks: [],
  projectStoreItems: [],
  projectStoreCategory: "all",
  hardwareStoreItems: [],
  hardwareStoreCategory: "all",
  bazaarItems: [],
  bazaarCategory: "all",
  offers: [],
  meetings: [],
  activeMeeting: null,
  analytics: null,
  charts: {},
  isAIChatOpen: false
};

const API_BASE = window.location.origin;

// Helper for authenticated API requests
async function authFetch(url, options = {}) {
  const headers = options.headers || {};
  if (state.sessionToken && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${state.sessionToken}`;
  }
  return fetch(url, {
    ...options,
    headers,
    credentials: "same-origin"
  });
}

// ==========================================
// APPLICATION INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
  // Initialize Zero-G Space Particle & Starfield Background
  initSpaceParticleCanvas();

  // Initialize Session & Authentication
  await initAuthSession();

  // Load initial background datasets
  await loadProjects();
  await loadMeetings();

  // Close dropdowns on outside click
  document.addEventListener("click", (e) => {
    const moreContainer = document.getElementById("nav-more-dropdown-container");
    const moreMenu = document.getElementById("nav-more-menu");
    if (moreContainer && !moreContainer.contains(e.target) && moreMenu && !moreMenu.classList.contains("hidden")) {
      closeMoreDropdown();
    }

    const userContainer = document.getElementById("user-profile-dropdown-container");
    const userMenu = document.getElementById("user-profile-dropdown");
    if (userContainer && !userContainer.contains(e.target) && userMenu && !userMenu.classList.contains("hidden")) {
      toggleUserDropdown(false);
    }
  });

  // Close mobile drawer on Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      toggleMobileDrawer(false);
      closeMoreDropdown();
      toggleUserDropdown(false);
    }
  });

  // Network offline/online listeners for 404 & telemetry
  window.addEventListener("online", updateNetworkStatus);
  window.addEventListener("offline", updateNetworkStatus);

  if (window.lucide) {
    lucide.createIcons();
  }
});

// ==========================================
// ZERO-G CANVAS PARTICLE STARFIELD
// ==========================================
function initSpaceParticleCanvas() {
  const canvas = document.getElementById("space-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  let width = (canvas.width = window.innerWidth);
  let height = (canvas.height = window.innerHeight);

  const particles = [];
  const numParticles = Math.min(Math.floor((width * height) / 16000), 90);
  const colors = ["#10b981", "#34d399", "#06b6d4", "#6366f1", "#a7f3d0", "#ffffff"];

  const mouse = { x: null, y: null, radius: 140 };

  window.addEventListener("mousemove", (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
  });

  window.addEventListener("mouseout", () => {
    mouse.x = null;
    mouse.y = null;
  });

  window.addEventListener("resize", () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  class StarParticle {
    constructor() {
      this.reset(true);
    }

    reset(initial = false) {
      this.x = Math.random() * width;
      this.y = initial ? Math.random() * height : Math.random() > 0.5 ? 0 : height;
      this.radius = Math.random() * 1.8 + 0.6;
      this.color = colors[Math.floor(Math.random() * colors.length)];
      this.alpha = Math.random() * 0.6 + 0.2;
      this.baseAlpha = this.alpha;
      this.vx = (Math.random() - 0.5) * 0.4;
      this.vy = (Math.random() - 0.5) * 0.4;
      this.twinkleSpeed = Math.random() * 0.02 + 0.005;
      this.pulse = Math.random() * Math.PI;
    }

    update() {
      this.x += this.vx;
      this.y += this.vy;

      // Mouse repulsion/interaction
      if (mouse.x !== null && mouse.y !== null) {
        const dx = mouse.x - this.x;
        const dy = mouse.y - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < mouse.radius) {
          const force = (mouse.radius - dist) / mouse.radius;
          const angle = Math.atan2(dy, dx);
          this.x -= Math.cos(angle) * force * 1.5;
          this.y -= Math.sin(angle) * force * 1.5;
        }
      }

      // Pulse alpha
      this.pulse += this.twinkleSpeed;
      this.alpha = this.baseAlpha + Math.sin(this.pulse) * 0.2;

      // Screen wrapping
      if (this.x < 0) this.x = width;
      if (this.x > width) this.x = 0;
      if (this.y < 0) this.y = height;
      if (this.y > height) this.y = 0;
    }

    draw() {
      ctx.save();
      ctx.globalAlpha = Math.max(0.1, Math.min(1, this.alpha));
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
      ctx.fillStyle = this.color;
      ctx.shadowBlur = this.radius > 1.4 ? 8 : 0;
      ctx.shadowColor = this.color;
      ctx.fill();
      ctx.restore();
    }
  }

  for (let i = 0; i < numParticles; i++) {
    particles.push(new StarParticle());
  }

  function renderStars() {
    ctx.clearRect(0, 0, width, height);

    // Draw subtle connecting constellation lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 85) {
          const lineAlpha = (1 - dist / 85) * 0.15;
          ctx.save();
          ctx.strokeStyle = `rgba(52, 211, 153, ${lineAlpha})`;
          ctx.lineWidth = 0.6;
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
          ctx.restore();
        }
      }
    }

    // Update & draw each star particle
    for (let i = 0; i < particles.length; i++) {
      particles[i].update();
      particles[i].draw();
    }

    requestAnimationFrame(renderStars);
  }

  requestAnimationFrame(renderStars);
}

// ==========================================
// ==========================================
// ==========================================
// AUTHENTICATION & SESSION ENGINE
// ==========================================
async function initAuthSession() {
  const token = localStorage.getItem("proversed_session_token");
  if (token) {
    state.sessionToken = token;
  }

  try {
    const res = await authFetch(`${API_BASE}/api/auth/session`);
    if (res.ok) {
      const data = await res.json();
      if (data.valid && data.user) {
        state.currentUser = data.user;
        state.sessionInfo = data.session;
        state.isAuthenticated = true;
        updateUserUI();
        updateAnalyticsDashboardUI();
      } else {
        state.currentUser = null;
        state.isAuthenticated = false;
        state.sessionToken = null;
        localStorage.removeItem("proversed_session_token");
      }
    }
  } catch (err) {
    console.warn("Session check offline or error:", err);
  }

  // Handle URL path routing and reset tokens on load
  const urlParams = new URLSearchParams(window.location.search);
  const resetToken = urlParams.get("reset_token") || urlParams.get("token");

  const path = window.location.pathname.replace(/^\/+|\/+$/g, "");
  if (resetToken) {
    switchTab("login", false);
    setTimeout(() => {
      openResetPasswordModal(resetToken);
    }, 150);
  } else if (path === "login") {
    switchTab("login", false);
  } else if (path === "profile" || path === "dashboard" || path === "analytics") {
    switchTab(state.isAuthenticated ? "profile" : "login", false);
  } else if (path === "404" || path === "notfound") {
    switchTab("404", false);
  } else if (path && path !== "explore") {
    const knownPaths = ["profile", "kanban", "plagiarism", "projectStore", "project-store", "hardwareStore", "hardware-store", "bazaar", "deals", "meeting", "analytics", "dashboard"];
    if (knownPaths.includes(path)) {
      switchTab(path, false);
    } else {
      switchTab("404", false);
    }
  } else {
    // Default: If authenticated -> explore or profile, else login
    switchTab(state.isAuthenticated ? "explore" : "login", false);
  }
}


function setAuthMode(mode) {
  const loginForm = document.getElementById("auth-login-form");
  const regForm = document.getElementById("auth-register-form");
  const loginTabBtn = document.getElementById("auth-tab-btn-login");
  const regTabBtn = document.getElementById("auth-tab-btn-register");

  if (mode === "register") {
    if (loginForm) loginForm.classList.add("hidden");
    if (regForm) regForm.classList.remove("hidden");
    if (loginTabBtn) {
      loginTabBtn.className = "flex-1 py-2 rounded-lg text-slate-400 hover:text-white transition-all text-center";
    }
    if (regTabBtn) {
      regTabBtn.className = "flex-1 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 transition-all text-center";
    }
  } else {
    if (regForm) regForm.classList.add("hidden");
    if (loginForm) loginForm.classList.remove("hidden");
    if (regTabBtn) {
      regTabBtn.className = "flex-1 py-2 rounded-lg text-slate-400 hover:text-white transition-all text-center";
    }
    if (loginTabBtn) {
      loginTabBtn.className = "flex-1 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 transition-all text-center";
    }
  }
  dismissLoginAlert("login-error-alert");
}

function dismissLoginAlert(alertId) {
  const el = document.getElementById(alertId);
  if (el) el.classList.add("hidden");
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPass = input.type === "password";
  input.type = isPass ? "text" : "password";
  if (btn) {
    btn.innerHTML = isPass ? '<i data-lucide="eye-off" class="w-4 h-4"></i>' : '<i data-lucide="eye" class="w-4 h-4"></i>';
    if (window.lucide) lucide.createIcons();
  }
}

async function handleLoginSubmit(event) {
  event.preventDefault();
  const emailInput = document.getElementById("login-email");
  const passInput = document.getElementById("login-password");
  const rememberInput = document.getElementById("login-remember");
  const submitBtn = document.getElementById("login-submit-btn");
  const submitText = document.getElementById("login-submit-btn-text");

  const errAlert = document.getElementById("login-error-alert");
  const errText = document.getElementById("login-error-text");
  const lockoutAlert = document.getElementById("login-lockout-alert");
  const ratelimitAlert = document.getElementById("login-ratelimit-alert");

  if (errAlert) errAlert.classList.add("hidden");
  if (lockoutAlert) lockoutAlert.classList.add("hidden");
  if (ratelimitAlert) ratelimitAlert.classList.add("hidden");

  const email = emailInput ? emailInput.value.trim() : "";
  const password = passInput ? passInput.value : "";
  const remember = rememberInput ? rememberInput.checked : false;

  if (submitBtn) submitBtn.disabled = true;
  if (submitText) submitText.textContent = "Verifying Credentials...";

  try {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, remember_me: remember })
    });

    const data = await res.json().catch(() => ({}));

    if (res.status === 200 && data.session_token) {
      state.sessionToken = data.session_token;
      state.currentUser = data.user;
      state.isAuthenticated = true;
      localStorage.setItem("proversed_session_token", data.session_token);

      showToast(`Welcome back, ${data.user.name}! Authenticated.`);
      updateUserUI();
      updateAnalyticsDashboardUI();
      switchTab("explore");
      return;
    }

    // Handle 423 Account Lockout
    if (res.status === 423) {
      if (lockoutAlert) {
        lockoutAlert.classList.remove("hidden");
        startLockoutCountdown(data.remaining_lockout_seconds || 10800);
      }
      return;
    }

    // Handle 429 Rate Limit
    if (res.status === 429) {
      if (ratelimitAlert) {
        ratelimitAlert.classList.remove("hidden");
      }
      return;
    }

    // Handle Generic Authentication Failure (401)
    if (errAlert) {
      errAlert.classList.remove("hidden");
      if (errText) errText.textContent = data.detail || "Invalid email or password. Please try again.";
      errAlert.classList.remove("shake-error");
      void errAlert.offsetWidth; // Force reflow for shake animation
      errAlert.classList.add("shake-error");
    }

  } catch (netErr) {
    if (errAlert) {
      errAlert.classList.remove("hidden");
      if (errText) errText.textContent = "Network or connection error. Please try again.";
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (submitText) submitText.textContent = "Authenticate Session";
    if (window.lucide) lucide.createIcons();
  }
}

let otpCooldownInterval = null;
let isRegisterEmailVerified = false;

async function handleSendOtp() {
  const emailInput = document.getElementById("reg-email");
  const email = emailInput ? emailInput.value.trim() : "";
  const sendBtn = document.getElementById("reg-send-otp-btn");
  const sendText = document.getElementById("reg-send-otp-text");
  const resendBtn = document.getElementById("reg-resend-otp-btn");
  const otpGroup = document.getElementById("reg-otp-group");

  if (!email || !email.includes("@")) {
    showToast("Please enter a valid institutional or Gmail address before requesting an OTP.", "error");
    if (emailInput) emailInput.focus();
    return;
  }

  if (sendBtn) sendBtn.disabled = true;
  if (sendText) sendText.textContent = "Sending...";
  if (resendBtn) resendBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/auth/send-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      showToast(data.detail || "Failed to send OTP. Please try again.", "error");
      if (sendBtn) sendBtn.disabled = false;
      if (sendText) sendText.textContent = "Send OTP";
      if (resendBtn) resendBtn.disabled = false;
      return;
    }

    if (otpGroup) {
      otpGroup.classList.remove("hidden");
    }

    const otpInput = document.getElementById("reg-otp");
    if (otpInput) {
      otpInput.focus();
      if (data.otp && window.location.hostname === "localhost") {
        console.log(`[PRO-VERSED OTP] Verification Code for ${email}: ${data.otp}`);
      }
    }

    showToast(data.message || `OTP dispatched to ${email}! Valid for 10 minutes.`, "success");
    startOtpCooldown(60);
  } catch (err) {
    showToast("Network error while dispatching OTP.", "error");
    if (sendBtn) sendBtn.disabled = false;
    if (sendText) sendText.textContent = "Send OTP";
    if (resendBtn) resendBtn.disabled = false;
  }
}

function startOtpCooldown(seconds) {
  if (otpCooldownInterval) clearInterval(otpCooldownInterval);
  let remaining = seconds;

  const sendBtn = document.getElementById("reg-send-otp-btn");
  const sendText = document.getElementById("reg-send-otp-text");
  const resendBtn = document.getElementById("reg-resend-otp-btn");

  if (sendBtn) sendBtn.disabled = true;
  if (resendBtn) resendBtn.disabled = true;

  const update = () => {
    if (remaining <= 0) {
      clearInterval(otpCooldownInterval);
      if (sendBtn) sendBtn.disabled = false;
      if (sendText) sendText.textContent = "Resend";
      if (resendBtn) {
        resendBtn.disabled = false;
        resendBtn.textContent = "Resend OTP";
      }
    } else {
      if (sendText) sendText.textContent = `${remaining}s`;
      if (resendBtn) resendBtn.textContent = `Resend in ${remaining}s`;
      remaining--;
    }
  };

  update();
  otpCooldownInterval = setInterval(update, 1000);
}

async function handleVerifyOtp() {
  const emailInput = document.getElementById("reg-email");
  const otpInput = document.getElementById("reg-otp");
  const verifyBtn = document.getElementById("reg-verify-otp-btn");
  const verifyText = document.getElementById("reg-verify-otp-text");
  const verifiedBadge = document.getElementById("reg-email-verified-badge");

  const email = emailInput ? emailInput.value.trim() : "";
  const otp = otpInput ? otpInput.value.trim() : "";

  if (!email) {
    showToast("Please enter your email address.", "error");
    return;
  }

  if (!otp || otp.length < 4) {
    showToast("Please enter the 6-digit OTP code.", "error");
    if (otpInput) otpInput.focus();
    return;
  }

  if (verifyBtn) verifyBtn.disabled = true;
  if (verifyText) verifyText.textContent = "Checking...";

  try {
    const res = await fetch(`${API_BASE}/api/auth/verify-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, otp })
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      showToast(data.detail || "Invalid or expired OTP code.", "error");
      return;
    }

    isRegisterEmailVerified = true;
    if (verifiedBadge) verifiedBadge.classList.remove("hidden");
    if (verifyBtn) {
      verifyBtn.classList.remove("bg-gradient-to-r", "from-emerald-500", "to-teal-500");
      verifyBtn.classList.add("bg-emerald-500/20", "text-emerald-300", "border", "border-emerald-500/40");
      if (verifyText) verifyText.textContent = "Verified ✓";
    }
    showToast("Email address verified! Complete registration below.", "success");
  } catch (err) {
    showToast("Network error while verifying OTP.", "error");
  } finally {
    if (verifyBtn && !isRegisterEmailVerified) {
      verifyBtn.disabled = false;
      if (verifyText) verifyText.textContent = "Verify";
    }
  }
}

async function handleRegisterSubmit(event) {
  event.preventDefault();
  const name = document.getElementById("reg-name")?.value.trim() || "";
  const email = document.getElementById("reg-email")?.value.trim() || "";
  const password = document.getElementById("reg-password")?.value || "";
  const role = document.getElementById("reg-role")?.value || "student";
  const college = document.getElementById("reg-college")?.value.trim() || "";
  const otpInput = document.getElementById("reg-otp");
  const otp = otpInput ? otpInput.value.trim() : "";

  const submitBtn = document.getElementById("reg-submit-btn");

  if (!email || !email.includes("@")) {
    showToast("Please enter a valid email address.", "error");
    return;
  }

  if (!otp && !isRegisterEmailVerified) {
    showToast("Please request and enter your 6-digit email OTP.", "error");
    handleSendOtp();
    return;
  }

  if (submitBtn) submitBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fullName: name,
        name: name,
        email: email,
        password: password,
        role: role,
        collegeCompany: college,
        college: college,
        otp: otp
      })
    });

    const data = await res.json().catch(() => ({}));

    if (res.status === 200 && data.session_token) {
      state.sessionToken = data.session_token;
      state.currentUser = data.user;
      state.isAuthenticated = true;
      localStorage.setItem("proversed_session_token", data.session_token);

      showToast(`Account created! Welcome to Pro-Versed, ${data.user.name}.`, "success");
      updateUserUI();
      updateAnalyticsDashboardUI();
      switchTab("explore");
    } else {
      showToast(data.detail || "Registration failed. Please check your inputs.", "error");
    }
  } catch (e) {
    showToast("Network error during registration.", "error");
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function handleLogout() {
  try {
    await authFetch(`${API_BASE}/api/auth/logout`, { method: "POST" });
  } catch (e) { }

  state.currentUser = null;
  state.isAuthenticated = false;
  state.sessionToken = null;
  state.sessionInfo = null;
  localStorage.removeItem("proversed_session_token");

  // Completely hide the navbar and AI widget on sign out
  const header = document.getElementById("main-floating-navbar");
  if (header) header.classList.add("hidden");
  const aiChatWidget = document.getElementById("ai-chat-container");
  if (aiChatWidget) aiChatWidget.classList.add("hidden");

  showToast("Session successfully revoked. Signed out.");
  updateUserUI();
  switchTab("login");
}

async function fillAndLoginPersona(userId, email) {
  const emailEl = document.getElementById("login-email");
  const passEl = document.getElementById("login-password");
  if (emailEl && email) emailEl.value = email;
  if (passEl) passEl.value = "Password123!";

  // Trigger instant authenticated demo sign-in
  try {
    const res = await fetch(`${API_BASE}/api/auth/demo-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId })
    });
    if (res.ok) {
      const data = await res.json();
      state.sessionToken = data.session_token;
      state.currentUser = data.user;
      state.isAuthenticated = true;
      localStorage.setItem("proversed_session_token", data.session_token);

      showToast(`Signed in as ${data.user.name} (${data.user.role})`);
      updateUserUI();
      updateAnalyticsDashboardUI();

      // Route to default view based on role
      switchTab("explore");
    }
  } catch (err) {
    console.warn("Demo login error:", err);
  }
}

function startLockoutCountdown(seconds) {
  if (state.lockoutTimerInterval) {
    clearInterval(state.lockoutTimerInterval);
  }

  let remaining = seconds;
  const countdownEl = document.getElementById("lockout-countdown");

  function update() {
    if (remaining <= 0) {
      clearInterval(state.lockoutTimerInterval);
      dismissLoginAlert("login-lockout-alert");
      return;
    }
    const hrs = Math.floor(remaining / 3600);
    const mins = Math.floor((remaining % 3600) / 60);
    const secs = remaining % 60;
    const formatted = `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    if (countdownEl) countdownEl.textContent = formatted;
    remaining--;
  }

  update();
  state.lockoutTimerInterval = setInterval(update, 1000);
}

function copySessionToken() {
  if (!state.sessionToken) return;
  navigator.clipboard.writeText(state.sessionToken).then(() => {
    showToast("Session token copied to clipboard!");
  }).catch(() => {
    showToast("Could not copy token automatically.", true);
  });
}

// ==========================================
// NETWORK STATUS & DIAGNOSTICS
// ==========================================

function updateNetworkStatus() {
  const isOnline = navigator.onLine;
  const badge = document.getElementById("diag-network-badge");
  if (badge) {
    badge.textContent = isOnline ? "ONLINE" : "OFFLINE";
    badge.className = isOnline
      ? "px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-sans font-bold"
      : "px-2 py-0.5 rounded text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/20 font-sans font-bold";
  }
}

async function runDiagnosticCheck() {
  const apiStatusEl = document.getElementById("diag-api-status");
  if (apiStatusEl) apiStatusEl.textContent = "Testing ping latency...";
  const start = performance.now();
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    const latency = Math.round(performance.now() - start);
    if (res.ok) {
      if (apiStatusEl) apiStatusEl.textContent = `Operational (200 OK, ${latency}ms)`;
    } else {
      if (apiStatusEl) apiStatusEl.textContent = `Error ${res.status}`;
    }
  } catch (e) {
    if (apiStatusEl) apiStatusEl.textContent = "API Unreachable (Network Error)";
  }
}

// ==========================================
// NAVIGATION & TAB ROUTING
// ==========================================
function switchTab(tabName, updateHistory = true) {
  // Normalize 404 & Aliases
  if (tabName === "notfound" || tabName === "404") {
    tabName = "404";
  }
  if (tabName === "dashboard" || tabName === "analytics") {
    tabName = "profile";
  }

  // REQUIREMENT 1: Hide Navbar on Sign-In / Auth Page or Unauthenticated State
  const header = document.getElementById("main-floating-navbar");
  const aiChatWidget = document.getElementById("ai-chat-container");

  if (tabName === "login" || !state.isAuthenticated) {
    if (header) header.classList.add("hidden");
    if (aiChatWidget) aiChatWidget.classList.add("hidden");
  } else {
    if (header) header.classList.remove("hidden");
    if (aiChatWidget) aiChatWidget.classList.remove("hidden");
  }

  // Protected Route Check
  if (tabName !== "login" && tabName !== "404" && !state.isAuthenticated) {
    showToast("Please sign in to access this portal.", true);
    switchTab("login", updateHistory);
    return;
  }

  // If already authenticated and navigating to login -> redirect to explore
  if (tabName === "login" && state.isAuthenticated) {
    switchTab("explore", updateHistory);
    return;
  }

  // REQUIREMENT 6: RBAC Protection - Block Industrialist from Hardware Store
  if (state.currentUser && (state.currentUser.role === "industrialist" || state.currentUser.role === "buyer") && (tabName === "hardwareStore" || tabName === "hardware-store" || tabName === "bazaar")) {
    showToast("Hardware Store is reserved for student creators and academic labs.", true);
    switchTab("deals", updateHistory);
    return;
  }

  state.activeTab = tabName;

  const views = {
    login: document.getElementById("view-login"),
    profile: document.getElementById("view-profile"),
    dashboard: document.getElementById("view-profile") || document.getElementById("view-dashboard"),
    "404": document.getElementById("view-404"),
    explore: document.getElementById("view-explore"),
    kanban: document.getElementById("view-kanban"),
    plagiarism: document.getElementById("view-plagiarism"),
    projectStore: document.getElementById("view-project-store"),
    "project-store": document.getElementById("view-project-store"),
    hardwareStore: document.getElementById("view-hardware-store"),
    "hardware-store": document.getElementById("view-hardware-store"),
    bazaar: document.getElementById("view-hardware-store") || document.getElementById("view-project-store") || document.getElementById("view-bazaar"),
    deals: document.getElementById("view-deals"),
    meeting: document.getElementById("view-meeting"),
    analytics: document.getElementById("view-profile")
  };

  const navBtns = {
    profile: document.getElementById("nav-btn-profile") || document.getElementById("drawer-btn-profile"),
    analytics: document.getElementById("nav-btn-profile") || document.getElementById("drawer-btn-profile"),
    dashboard: document.getElementById("nav-btn-profile") || document.getElementById("drawer-btn-profile"),
    explore: document.getElementById("nav-btn-explore"),
    kanban: document.getElementById("nav-btn-kanban"),
    plagiarism: document.getElementById("nav-btn-plagiarism"),
    projectStore: document.getElementById("nav-btn-project-store"),
    "project-store": document.getElementById("nav-btn-project-store"),
    hardwareStore: document.getElementById("nav-btn-hardware-store"),
    "hardware-store": document.getElementById("nav-btn-hardware-store"),
    bazaar: document.getElementById("nav-btn-hardware-store") || document.getElementById("nav-btn-project-store") || document.getElementById("nav-btn-bazaar"),
    deals: document.getElementById("nav-btn-deals"),
    meeting: document.getElementById("nav-btn-meeting")
  };

  Object.keys(views).forEach(k => {
    if (views[k]) views[k].classList.add("hidden");
  });

  Object.keys(navBtns).forEach(k => {
    if (navBtns[k]) {
      navBtns[k].classList.remove("nav-tab-active", "text-emerald-400", "bg-emerald-600/20", "border-emerald-500/40");
      navBtns[k].classList.add("text-slate-400", "border-transparent");
    }
  });

  // Activate view
  const targetView = views[tabName] || (tabName === "profile" ? views["profile"] : null) || views["404"];
  if (targetView) {
    targetView.classList.remove("hidden");
  }

  if (navBtns[tabName]) {
    navBtns[tabName].classList.add("nav-tab-active");
    navBtns[tabName].classList.remove("text-slate-400", "border-transparent");
  }

  // Update More button active state indicator if secondary tab is selected
  const moreBtn = document.getElementById("nav-more-btn");
  const secondaryTabs = ["plagiarism", "projectStore", "project-store", "hardwareStore", "hardware-store", "bazaar", "deals", "meeting"];
  if (moreBtn) {
    if (secondaryTabs.includes(tabName)) {
      moreBtn.classList.add("nav-tab-active", "text-emerald-400");
      moreBtn.classList.remove("text-slate-400", "border-transparent");
    } else {
      moreBtn.classList.remove("nav-tab-active", "text-emerald-400");
      moreBtn.classList.add("text-slate-400", "border-transparent");
    }
  }

  if (updateHistory) {
    const pushPath = tabName === "explore" ? "/" : `/${tabName}`;
    try {
      window.history.pushState({ tab: tabName }, "", pushPath);
    } catch (e) { }
  }

  if (tabName === "profile" || tabName === "analytics" || tabName === "dashboard") {
    updateUserUI();
    loadUserProfile();
  } else if (tabName === "404") {
    const urlPathEl = document.getElementById("diag-url-path");
    if (urlPathEl) urlPathEl.textContent = window.location.pathname || "/unknown-route";
    updateNetworkStatus();
    runDiagnosticCheck();
  } else if (tabName === "kanban") {
    loadKanbanBoard();
  } else if (tabName === "plagiarism") {
    loadPlagiarismAuditLogs();
  } else if (tabName === "projectStore" || tabName === "project-store") {
    loadProjectStore();
  } else if (tabName === "hardwareStore" || tabName === "hardware-store") {
    loadHardwareStore();
  } else if (tabName === "bazaar") {
    loadHardwareStore();
    loadProjectStore();
  } else if (tabName === "deals") {
    loadIndustrialOffers();
  } else if (tabName === "meeting") {
    loadMeetings();
  } else if (tabName === "explore") {
    loadProjects();
  }

  setTimeout(() => {
    if (window.lucide) lucide.createIcons();
  }, 50);
}

// Handle Browser Back/Forward buttons
window.addEventListener("popstate", () => {
  const path = window.location.pathname.replace(/^\/+|\/+$/g, "");
  const known = ["login", "profile", "dashboard", "404", "explore", "kanban", "plagiarism", "projectStore", "project-store", "hardwareStore", "hardware-store", "bazaar", "deals", "meeting", "analytics"];
  if (known.includes(path)) {
    switchTab(path, false);
  } else if (!path) {
    switchTab(state.isAuthenticated ? "explore" : "login", false);
  } else {
    switchTab("404", false);
  }
});


// ==========================================
// DROPDOWNS & RESPONSIVE SLIDE-OUT DRAWER
// ==========================================
function toggleMoreDropdown(forceState) {
  const menu = document.getElementById("nav-more-menu");
  const chevron = document.getElementById("more-chevron");
  if (!menu) return;

  const isHidden = menu.classList.contains("hidden");
  const shouldOpen = forceState !== undefined ? forceState : isHidden;

  if (shouldOpen) {
    menu.classList.remove("hidden");
    if (chevron) chevron.classList.add("rotate-180");
  } else {
    menu.classList.add("hidden");
    if (chevron) chevron.classList.remove("rotate-180");
  }
}

function closeMoreDropdown() {
  toggleMoreDropdown(false);
}

function toggleUserDropdown(forceState) {
  const menu = document.getElementById("user-profile-dropdown");
  if (!menu) return;

  const isHidden = menu.classList.contains("hidden");
  const shouldOpen = forceState !== undefined ? forceState : isHidden;

  if (shouldOpen) {
    menu.classList.remove("hidden");
  } else {
    menu.classList.add("hidden");
  }
}

function toggleMobileDrawer(forceState) {
  const drawer = document.getElementById("mobile-nav-drawer");
  const hamburgerIcon = document.getElementById("hamburger-icon");
  if (!drawer) return;

  const isHidden = drawer.classList.contains("hidden");
  const shouldOpen = forceState !== undefined ? forceState : isHidden;

  if (shouldOpen) {
    drawer.classList.remove("hidden");
    document.body.style.overflow = "hidden";
    if (hamburgerIcon) {
      hamburgerIcon.setAttribute("data-lucide", "x");
    }
  } else {
    drawer.classList.add("hidden");
    document.body.style.overflow = "";
    if (hamburgerIcon) {
      hamburgerIcon.setAttribute("data-lucide", "menu");
    }
  }

  if (window.lucide) lucide.createIcons();
}

// ==========================================
// USER PERSONAS & ROLE SWITCHER (DEMO MODE)
// ==========================================
function updateUserUI() {
  const u = state.currentUser || {
    id: "usr_guest",
    name: "Guest Innovator",
    email: "Sign in to access ecosystem",
    role: "student",
    college: "Pro-Versed Portal",
    avatar_url: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80"
  };

  // Navbar Header Pill
  const avatarEl = document.getElementById("user-avatar");
  const nameEl = document.getElementById("user-name");
  const badgeEl = document.getElementById("user-badge");
  const roleCollegeEl = document.getElementById("user-role-college");

  // User Profile Dropdown Elements
  const dropdownAvatarEl = document.getElementById("dropdown-user-avatar");
  const dropdownNameEl = document.getElementById("dropdown-user-name");
  const dropdownEmailEl = document.getElementById("dropdown-user-email");
  const dropdownBadgeEl = document.getElementById("dropdown-user-badge");
  const dropdownInstitutionEl = document.getElementById("dropdown-user-institution");

  // Mobile Drawer Profile Elements
  const drawerAvatarEl = document.getElementById("drawer-user-avatar");
  const drawerNameEl = document.getElementById("drawer-user-name");
  const drawerRoleEl = document.getElementById("drawer-user-role");

  if (avatarEl && u.avatar_url) avatarEl.src = u.avatar_url;
  if (dropdownAvatarEl && u.avatar_url) dropdownAvatarEl.src = u.avatar_url;
  if (drawerAvatarEl && u.avatar_url) drawerAvatarEl.src = u.avatar_url;

  if (nameEl) nameEl.textContent = u.name;
  if (dropdownNameEl) dropdownNameEl.textContent = u.name;
  if (drawerNameEl) drawerNameEl.textContent = u.name;
  if (dropdownEmailEl) dropdownEmailEl.textContent = u.email || "innovator@proversed.in";

  let roleLabel = state.isAuthenticated ? "Student" : "Unauthenticated";
  let badgeClasses = state.isAuthenticated ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" : "bg-slate-700/40 text-slate-400 border-slate-600/40";

  if (state.isAuthenticated) {
    if (u.role === "student") {
      roleLabel = "Student";
      badgeClasses = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    } else if (u.role === "faculty") {
      roleLabel = "Faculty Mentor";
      badgeClasses = "bg-indigo-500/20 text-indigo-300 border-indigo-500/30";
    } else if (u.role === "spoc") {
      roleLabel = "Campus Coordinator";
      badgeClasses = "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";
    } else if (u.role === "industrialist" || u.role === "buyer") {
      roleLabel = "Industrial Partner";
      badgeClasses = "bg-amber-500/20 text-amber-300 border-amber-500/30";
    } else if (u.role === "admin") {
      roleLabel = "Platform Admin";
      badgeClasses = "bg-rose-500/20 text-rose-300 border-rose-500/30";
    }
  }

  if (badgeEl) {
    badgeEl.textContent = roleLabel;
    badgeEl.className = `text-[10px] font-bold px-1.5 py-0.2 rounded border ${badgeClasses}`;
  }
  if (dropdownBadgeEl) {
    dropdownBadgeEl.textContent = roleLabel;
    dropdownBadgeEl.className = `text-[9px] font-bold px-1.5 py-0.2 rounded border ${badgeClasses}`;
  }
  if (drawerRoleEl) {
    drawerRoleEl.textContent = roleLabel;
  }

  const institution = u.company ? u.company : (u.college || "Bharat Academic Network");
  if (roleCollegeEl) {
    roleCollegeEl.textContent = institution;
  }
  if (dropdownInstitutionEl) {
    dropdownInstitutionEl.textContent = institution;
  }

  // Profile Dashboard Header Profile Card
  const profAvatarEl = document.getElementById("profile-user-avatar");
  const profNameEl = document.getElementById("profile-user-name");
  const profRoleEl = document.getElementById("profile-user-role");
  const profCollegeEl = document.getElementById("profile-user-college");
  const profEmailEl = document.getElementById("profile-user-email");

  if (profAvatarEl && u.avatar_url) profAvatarEl.src = u.avatar_url;
  if (profNameEl) profNameEl.textContent = u.name;
  if (profEmailEl) profEmailEl.textContent = u.email || "innovator@proversed.in";
  if (profCollegeEl) profCollegeEl.textContent = institution;
  if (profRoleEl) {
    profRoleEl.textContent = roleLabel;
    profRoleEl.className = `px-2.5 py-0.5 rounded-full text-xs font-bold ${badgeClasses}`;
  }

  // Dashboard Analytics Header Profile Card
  const dashAvatarEl = document.getElementById("dash-user-avatar");
  const dashNameEl = document.getElementById("dash-user-name");
  const dashRoleBadgeEl = document.getElementById("dash-user-role-badge");
  const dashVerifiedEl = document.getElementById("dash-user-verified");
  const dashEmailEl = document.getElementById("dash-user-email");
  const dashCollegeEl = document.getElementById("dash-user-college");

  if (dashAvatarEl) {
    const initials = u.name ? u.name.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase() : "AP";
    dashAvatarEl.textContent = initials;
  }
  if (dashNameEl) dashNameEl.textContent = u.name;
  if (dashEmailEl) dashEmailEl.textContent = u.email || "innovator@proversed.in";
  if (dashCollegeEl) dashCollegeEl.textContent = institution;
  if (dashRoleBadgeEl) {
    dashRoleBadgeEl.textContent = roleLabel;
    dashRoleBadgeEl.className = `px-2.5 py-0.5 rounded-full text-xs font-bold ${badgeClasses}`;
  }
  if (dashVerifiedEl) {
    dashVerifiedEl.textContent = (u.role === "industrialist" || u.role === "buyer") ? "Verified Industry Partner" : "Verified Academic";
  }

  // REQUIREMENT 5: Hide "Submit Project" from Faculty Mentors, Campus SPOCs & Industrial Partners
  // Only Students and Platform Admins can submit new projects
  const isStudentOrAdmin = state.isAuthenticated && (u.role === "student" || u.role === "admin");
  const headerSubmitBtn = document.getElementById("btn-header-submit-project") || document.getElementById("nav-cta-btn");
  const exploreSubmitBtn = document.getElementById("btn-explore-submit-project");
  const drawerSubmitBtn = document.getElementById("btn-drawer-submit-project");

  if (headerSubmitBtn) headerSubmitBtn.classList.toggle("hidden", !isStudentOrAdmin);
  if (exploreSubmitBtn) exploreSubmitBtn.classList.toggle("hidden", !isStudentOrAdmin);
  if (drawerSubmitBtn) drawerSubmitBtn.classList.toggle("hidden", !isStudentOrAdmin);

  // REQUIREMENT 6: Hide Hardware Store from Industrial Partners (Software Project Store remains accessible)
  const isIndustrialist = state.isAuthenticated && (u.role === "industrialist" || u.role === "buyer");
  const hardwareNavBtn = document.getElementById("nav-btn-hardware-store");
  const drawerHardwareBtn = document.getElementById("drawer-btn-hardware-store");
  const bazaarNavBtn = document.getElementById("nav-btn-bazaar");
  const drawerBazaarBtn = document.getElementById("drawer-btn-bazaar");

  if (hardwareNavBtn) hardwareNavBtn.classList.toggle("hidden", isIndustrialist);
  if (drawerHardwareBtn) drawerHardwareBtn.classList.toggle("hidden", isIndustrialist);
  if (bazaarNavBtn) bazaarNavBtn.classList.toggle("hidden", isIndustrialist);
  if (drawerBazaarBtn) drawerBazaarBtn.classList.toggle("hidden", isIndustrialist);

  if (isIndustrialist && (state.activeTab === "hardwareStore" || state.activeTab === "hardware-store" || state.activeTab === "bazaar")) {
    switchTab("deals");
  }
}

function openDemoModal() {
  openModal("modal-demo");
}

async function selectDemoPersona(userId) {
  try {
    // Normalization mapping for demo personas
    const personaMap = {
      "usr_student_01": "usr_student_1",
      "usr_faculty_01": "usr_faculty_1",
      "usr_spoc_01": "usr_spoc_1",
      "usr_buyer_01": "usr_industrialist_1",
      "usr_admin_01": "usr_admin_1",
      "student": "usr_student_1",
      "faculty": "usr_faculty_1",
      "spoc": "usr_spoc_1",
      "industrialist": "usr_industrialist_1",
      "admin": "usr_admin_1"
    };
    const targetId = personaMap[userId] || userId;

    await fillAndLoginPersona(targetId, "");
    closeModal("modal-demo");
    toggleUserDropdown(false);
    toggleMobileDrawer(false);
  } catch (err) {
    showToast(`Persona switch error: ${err.message}`, true);
  }
}

// ==========================================
// 1. EXPLORE PROJECTS & DISCOVERY HUB
// ==========================================
let searchDebounceTimer = null;
function debounceSearch() {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    loadProjects();
  }, 250);
}

async function loadProjects() {
  const searchInput = document.getElementById("search-input");
  const domainSelect = document.getElementById("filter-domain");
  const categorySelect = document.getElementById("filter-category");
  const lifecycleSelect = document.getElementById("filter-lifecycle");
  const collegeSelect = document.getElementById("filter-college");

  const search = searchInput ? searchInput.value.trim() : "";
  const domain = domainSelect ? domainSelect.value : "";
  const category = categorySelect ? categorySelect.value : "";
  const lifecycle = lifecycleSelect ? lifecycleSelect.value : "";
  const college = collegeSelect ? collegeSelect.value : "";

  const params = new URLSearchParams();
  if (search) params.append("search", search);
  if (domain) params.append("domain", domain);
  if (category) params.append("category", category);
  if (lifecycle) params.append("lifecycle", lifecycle);
  if (college) params.append("college", college);

  try {
    const res = await fetch(`${API_BASE}/api/projects?${params.toString()}`);
    if (!res.ok) throw new Error("Could not load projects.");
    const data = await res.json();
    state.projects = data;

    const countBadge = document.getElementById("projects-count-badge");
    if (countBadge) {
      countBadge.textContent = `${data.length} ${data.length === 1 ? 'project' : 'projects'}`;
    }

    renderProjectsGrid(data);
    populateKanbanSelect(data);
    populateMeetingProjectsSelect(data);
  } catch (err) {
    console.error("Error loading projects:", err);
    showToast("Error loading project repository.", "error");
  }
}

function renderProjectsGrid(projects) {
  const grid = document.getElementById("projects-grid");
  if (!grid) return;

  if (projects.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full py-16 text-center glass-panel rounded-3xl p-8 border border-white/[0.08]">
        <div class="w-16 h-16 rounded-2xl bg-white/[0.05] flex items-center justify-center mx-auto mb-4 text-slate-400">
          <i data-lucide="folder-search" class="w-8 h-8"></i>
        </div>
        <h4 class="text-lg font-bold text-white font-heading">No Projects Found</h4>
        <p class="text-sm text-slate-400 mt-1 max-w-md mx-auto">
          No innovations match your search criteria. Try adjusting your filters or submit a new student project.
        </p>
        <button onclick="openNewProjectModal()" class="mt-4 btn-glow-primary px-5 py-2.5 rounded-xl text-xs font-bold inline-flex items-center space-x-2">
          <i data-lucide="plus" class="w-4 h-4"></i>
          <span>Submit Project</span>
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  grid.innerHTML = projects.map(p => {
    let stageColor = "bg-slate-800 text-slate-300 border-slate-700";
    let stageLabel = p.lifecycle || "In Development";
    if (p.lifecycle === "Ideation") stageLabel = "1. Idea Phase";
    else if (p.lifecycle === "In Development") stageLabel = "2. In Development";
    else if (p.lifecycle === "Prototype Ready") stageLabel = "3. Prototype Ready";
    else if (p.lifecycle === "Completed") stageLabel = "4. Completed";
    else if (p.lifecycle === "Research Published") stageLabel = "5. Research Published";

    if (p.lifecycle === "Prototype Ready") {
      stageColor = "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";
    } else if (p.lifecycle === "In Development") {
      stageColor = "bg-indigo-500/20 text-indigo-300 border-indigo-500/30";
    } else if (p.lifecycle === "Completed" || p.lifecycle === "Research Published") {
      stageColor = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    }

    const originality = p.plagiarism_score ? (100 - p.plagiarism_score).toFixed(0) : "96";
    const originalityColor = originality >= 85 ? "text-emerald-400" : originality >= 70 ? "text-amber-400" : "text-rose-400";

    let techTags = [];
    try {
      techTags = Array.isArray(p.tech_stack) ? p.tech_stack : JSON.parse(p.tech_stack || "[]");
    } catch (e) {
      techTags = (p.tech_stack || "").split(",").map(t => t.trim()).filter(Boolean);
    }

    return `
      <div class="glass-panel glass-panel-hover rounded-3xl p-6 border border-white/[0.08] flex flex-col justify-between group">
        <div class="space-y-4">
          <div class="flex items-center justify-between gap-2">
            <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-white/[0.05] text-slate-300 border border-white/[0.08]">
              ${p.category || 'Innovation'}
            </span>
            <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${stageColor}">
              ${stageLabel}
            </span>
          </div>

          <div>
            <div class="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-1">${p.domain || 'Engineering'}</div>
            <h3 class="text-lg font-bold text-white group-hover:text-emerald-300 transition-colors line-clamp-2 font-heading">
              ${p.title}
            </h3>
          </div>

          <p class="text-xs text-slate-300 line-clamp-3 leading-relaxed">
            ${p.abstract || 'No technical summary provided.'}
          </p>

          <div class="flex flex-wrap gap-1.5 pt-1">
            ${techTags.slice(0, 3).map(t => `
              <span class="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/[0.04] text-slate-300 border border-white/[0.06]">${t}</span>
            `).join('')}
            ${techTags.length > 3 ? `<span class="text-[10px] font-mono px-1.5 py-0.5 text-slate-500">+${techTags.length - 3}</span>` : ''}
          </div>
        </div>

        <div class="pt-5 mt-4 border-t border-white/[0.06] space-y-3">
          <div class="flex items-center justify-between text-xs text-slate-400">
            <div class="flex items-center space-x-1.5">
              <i data-lucide="graduation-cap" class="w-3.5 h-3.5 text-slate-400"></i>
              <span class="font-medium text-slate-300 truncate max-w-[130px]">${p.college || 'IIT Bombay'}</span>
            </div>
            <div class="flex items-center space-x-1 font-bold ${originalityColor}">
              <i data-lucide="shield-check" class="w-3.5 h-3.5"></i>
              <span>${originality}% Unique</span>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2 pt-1">
            <button onclick="openProjectDetails('${p.id}')" class="btn-glow-secondary py-2 rounded-xl text-xs font-bold flex items-center justify-center space-x-1 cursor-pointer">
              <i data-lucide="eye" class="w-3.5 h-3.5"></i>
              <span>View Details</span>
            </button>
            <button onclick="quickOpenKanban('${p.id}')" class="btn-glow-primary py-2 rounded-xl text-xs font-bold flex items-center justify-center space-x-1 cursor-pointer">
              <i data-lucide="layout-grid" class="w-3.5 h-3.5"></i>
              <span>Task Board</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

async function openProjectDetails(projectId) {
  try {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}`);
    if (!res.ok) throw new Error("Could not load project details.");
    const p = await res.json();
    state.selectedProject = p;

    document.getElementById("detail-title").textContent = p.title;
    document.getElementById("detail-category-badge").textContent = p.category || "Innovation";
    document.getElementById("detail-domain-badge").textContent = p.domain || "Technology";
    document.getElementById("detail-college").innerHTML = `${p.college || 'IIT Bombay'} • Lead: <span id="detail-lead" class="text-slate-200 font-semibold">${p.lead_student_name || 'Aarav Sharma'}</span>`;
    document.getElementById("detail-abstract").textContent = p.abstract || "No abstract provided.";

    const originality = p.plagiarism_score ? (100 - p.plagiarism_score).toFixed(0) : "96";
    document.getElementById("detail-originality").textContent = `${originality}% Unique`;
    document.getElementById("detail-patent").textContent = p.patent_status || "Provisional Filed";

    // Generate/display deterministic IPFS CID
    const ipfsCid = "Qm" + btoa(p.title + p.id).replace(/[^a-zA-Z0-9]/g, "").substring(0, 44);
    const cidEl = document.getElementById("detail-ipfs-cid");
    if (cidEl) cidEl.textContent = ipfsCid;

    // Tech stack
    const techEl = document.getElementById("detail-tech-stack");
    let tech = [];
    try {
      tech = Array.isArray(p.tech_stack) ? p.tech_stack : JSON.parse(p.tech_stack || "[]");
    } catch (e) {
      tech = (p.tech_stack || "").split(",").map(t => t.trim()).filter(Boolean);
    }
    techEl.innerHTML = tech.map(t => `
      <span class="px-2.5 py-1 rounded-lg text-xs font-mono bg-white/[0.05] text-slate-200 border border-white/[0.08]">${t}</span>
    `).join('') || '<span class="text-xs text-slate-500">None listed</span>';

    // BOM table
    const bomTbody = document.getElementById("detail-bom-tbody");
    let bomList = [];
    try {
      bomList = Array.isArray(p.bom_components) ? p.bom_components : JSON.parse(p.bom_components || "[]");
    } catch (e) {
      bomList = [];
    }

    let totalBudget = 0;
    if (bomList.length > 0) {
      bomTbody.innerHTML = bomList.map(item => {
        const qty = item.quantity || item.qty || 1;
        const cost = item.cost || item.unit_cost || 0;
        const sub = qty * cost;
        totalBudget += sub;
        return `
          <tr>
            <td class="py-2.5 px-3 font-medium text-slate-200">${item.item || item.name || 'Component'}</td>
            <td class="py-2.5 px-3 text-slate-400">${qty}</td>
            <td class="py-2.5 px-3 text-slate-400">₹${cost.toLocaleString()}</td>
            <td class="py-2.5 px-3 font-semibold text-emerald-400">₹${sub.toLocaleString()}</td>
          </tr>
        `;
      }).join('');
    } else {
      bomTbody.innerHTML = `<tr><td colspan="4" class="py-3 px-3 text-center text-slate-500">No hardware components listed for this project.</td></tr>`;
    }

    document.getElementById("detail-bom-total").textContent = `₹${(totalBudget || p.estimated_budget || 25000).toLocaleString()}`;

    // Links
    const repoLink = document.getElementById("detail-repo-link");
    const demoLink = document.getElementById("detail-demo-link");
    if (p.repo_url) {
      repoLink.href = p.repo_url;
      repoLink.classList.remove("hidden");
    } else {
      repoLink.classList.add("hidden");
    }
    if (p.demo_url) {
      demoLink.href = p.demo_url;
      demoLink.classList.remove("hidden");
    } else {
      demoLink.classList.add("hidden");
    }

    document.getElementById("detail-kanban-btn").onclick = () => {
      closeModal("modal-project-details");
      quickOpenKanban(p.id);
    };

    document.getElementById("detail-bid-btn").onclick = () => {
      closeModal("modal-project-details");
      quickBid(p.id);
    };

    openModal("modal-project-details");
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    showToast("Could not open project details.", "error");
  }
}

function copyIPFSCID() {
  const cidEl = document.getElementById("detail-ipfs-cid");
  if (cidEl) {
    navigator.clipboard.writeText(cidEl.textContent.trim());
    showToast("IPFS Content Identifier (CID) copied to clipboard!", "success");
  }
}

function quickOpenKanban(projectId) {
  switchTab("kanban");
  const select = document.getElementById("kanban-project-select");
  if (select) {
    select.value = projectId;
    changeKanbanProject();
  }
}

function quickBid(projectId) {
  openSubmitOfferModal(projectId);
}

function updateProjectRepoVisibility() {
  const categorySelect = document.getElementById("create-proj-category");
  const repoContainer = document.getElementById("container-proj-repo");
  const urlsGrid = document.getElementById("container-proj-urls-grid");
  if (!categorySelect || !repoContainer) return;

  const isHardware = categorySelect.value === "Hardware Prototype";
  if (isHardware) {
    repoContainer.classList.add("hidden");
    if (urlsGrid) {
      urlsGrid.classList.remove("sm:grid-cols-3");
      urlsGrid.classList.add("sm:grid-cols-2");
    }
  } else {
    repoContainer.classList.remove("hidden");
    if (urlsGrid) {
      urlsGrid.classList.remove("sm:grid-cols-2");
      urlsGrid.classList.add("sm:grid-cols-3");
    }
  }
}

// Attach category change listener when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    const categorySelect = document.getElementById("create-proj-category");
    if (categorySelect) {
      categorySelect.addEventListener("change", updateProjectRepoVisibility);
    }
  });
} else {
  const categorySelect = document.getElementById("create-proj-category");
  if (categorySelect) {
    categorySelect.addEventListener("change", updateProjectRepoVisibility);
  }
}

function openNewProjectModal() {
  const form = document.getElementById("form-new-project");
  if (form) form.reset();
  openModal("modal-new-project");
  updateProjectRepoVisibility();
}

async function handleProjectSubmit(e) {
  e.preventDefault();
  const title = document.getElementById("create-proj-title").value.trim();
  const domain = document.getElementById("create-proj-domain").value;
  const category = document.getElementById("create-proj-category").value;
  const lifecycle = document.getElementById("create-proj-lifecycle").value;
  const abstract = document.getElementById("create-proj-abstract").value.trim();
  const tech = document.getElementById("create-proj-tech").value.trim();
  const budget = parseFloat(document.getElementById("create-proj-budget").value) || 0;
  const repo = document.getElementById("create-proj-repo").value.trim();
  const demo = document.getElementById("create-proj-demo").value.trim();

  const techArr = tech.split(",").map(t => t.trim()).filter(Boolean);

  const payload = {
    title,
    domain,
    category,
    lifecycle,
    abstract,
    tech_stack: techArr,
    estimated_budget: budget,
    repo_url: repo || null,
    demo_url: demo || null,
    college: state.currentUser.college || "IIT Bombay",
    lead_student_id: state.currentUser.id,
    lead_student_name: state.currentUser.name
  };

  try {
    const res = await fetch(`${API_BASE}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("Could not submit project.");
    const created = await res.json();

    closeModal("modal-new-project");
    const form = document.getElementById("form-new-project");
    if (form) form.reset();
    updateProjectRepoVisibility();
    showToast(`Project "${created.title}" successfully registered with IPFS hash!`, "success");

    await loadProjects();
  } catch (err) {
    showToast(`Submission failed: ${err.message}`, "error");
  }
}

// ==========================================
// 2. TASK & MILESTONE BOARD
// ==========================================
function populateKanbanSelect(projects) {
  const select = document.getElementById("kanban-project-select");
  const offerTargetSelect = document.getElementById("offer-target-project");
  if (!select) return;

  const currentVal = select.value;
  const optionsHtml = projects.map(p => `
    <option value="${p.id}">${p.title}</option>
  `).join('');

  select.innerHTML = optionsHtml;
  if (offerTargetSelect) offerTargetSelect.innerHTML = optionsHtml;

  if (currentVal && projects.some(p => p.id === currentVal)) {
    select.value = currentVal;
  }
}

function changeKanbanProject() {
  loadKanbanBoard();
}

async function loadKanbanBoard() {
  const select = document.getElementById("kanban-project-select");
  if (!select || !select.value) {
    if (state.projects.length > 0) {
      populateKanbanSelect(state.projects);
    }
  }

  const projectId = select ? select.value : (state.projects[0] ? state.projects[0].id : null);
  if (!projectId) return;

  const project = state.projects.find(p => p.id === projectId) || state.projects[0];
  if (project) {
    document.getElementById("kanban-project-title").textContent = project.title;
    document.getElementById("kanban-project-team").textContent = `Lead: ${project.lead_student_name || 'Aarav Sharma'} • College: ${project.college || 'IIT Bombay'}`;

    let stageLabel = project.lifecycle || "In Development";
    if (project.lifecycle === "Ideation") stageLabel = "1. Idea Phase";
    else if (project.lifecycle === "In Development") stageLabel = "2. In Development";
    else if (project.lifecycle === "Prototype Ready") stageLabel = "3. Prototype Ready";
    else if (project.lifecycle === "Completed") stageLabel = "4. Completed";
    else if (project.lifecycle === "Research Published") stageLabel = "5. Research Published";
    document.getElementById("kanban-project-stage").textContent = stageLabel;
  }

  try {
    const res = await fetch(`${API_BASE}/api/tasks?project_id=${projectId}`);
    if (!res.ok) throw new Error("Could not load milestone tasks.");
    const tasks = await res.json();
    state.tasks = tasks;

    const cols = {
      backlog: document.getElementById("col-backlog"),
      in_progress: document.getElementById("col-in_progress"),
      faculty_audit: document.getElementById("col-faculty_audit"),
      completed: document.getElementById("col-completed")
    };

    const counts = {
      backlog: document.getElementById("count-backlog"),
      in_progress: document.getElementById("count-in_progress"),
      faculty_audit: document.getElementById("count-faculty_audit"),
      completed: document.getElementById("count-completed")
    };

    Object.keys(cols).forEach(k => {
      if (cols[k]) cols[k].innerHTML = "";
    });

    const taskCounts = { backlog: 0, in_progress: 0, faculty_audit: 0, completed: 0 };

    tasks.forEach(t => {
      const colKey = t.column || "backlog";
      if (taskCounts[colKey] !== undefined) taskCounts[colKey]++;

      if (cols[colKey]) {
        cols[colKey].innerHTML += renderTaskCard(t);
      }
    });

    Object.keys(counts).forEach(k => {
      if (counts[k]) counts[k].textContent = taskCounts[k] || 0;
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Error loading task board:", err);
  }
}

function renderTaskCard(t) {
  let pColor = "bg-slate-800 text-slate-300 border-slate-700";
  if (t.priority === "urgent") pColor = "bg-rose-500/20 text-rose-300 border-rose-500/30";
  else if (t.priority === "high") pColor = "bg-amber-500/20 text-amber-300 border-amber-500/30";
  else if (t.priority === "medium") pColor = "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";

  const isMentor = state.currentUser.role === "faculty" || state.currentUser.role === "admin";
  const showMentorApprove = t.column === "faculty_audit" && isMentor;

  return `
    <div class="glass-panel p-4 rounded-2xl border border-white/[0.08] hover:border-emerald-500/40 transition-all space-y-3 shadow-md group">
      <div class="flex items-center justify-between gap-2">
        <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${pColor}">
          ${t.priority || 'Normal'}
        </span>
        ${t.due_date ? `<span class="text-[11px] text-slate-400 font-mono">📅 ${t.due_date}</span>` : ''}
      </div>

      <h4 class="text-sm font-bold text-white group-hover:text-emerald-300 transition-colors font-heading leading-snug">
        ${t.title}
      </h4>

      ${t.description ? `<p class="text-xs text-slate-300 leading-relaxed">${t.description}</p>` : ''}

      <div class="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-white/[0.05]">
        <div class="flex items-center space-x-1.5">
          <div class="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-bold">
            ${(t.assignee_name || 'A')[0]}
          </div>
          <span class="text-slate-300 truncate max-w-[100px]">${t.assignee_name || 'Assigned'}</span>
        </div>

        <div class="flex items-center space-x-1">
          ${t.column !== 'backlog' ? `
            <button onclick="moveTaskColumn('${t.id}', '${getPrevCol(t.column)}')" title="Move Left" class="p-1 rounded-lg hover:bg-white/[0.08] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="chevron-left" class="w-3.5 h-3.5"></i>
            </button>
          ` : ''}
          ${t.column !== 'completed' ? `
            <button onclick="moveTaskColumn('${t.id}', '${getNextCol(t.column)}')" title="Move Right" class="p-1 rounded-lg hover:bg-white/[0.08] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i>
            </button>
          ` : ''}
        </div>
      </div>

      ${showMentorApprove ? `
        <div class="pt-2">
          <button onclick="approveFacultyAuditTask('${t.id}')" class="w-full btn-glow-primary py-1.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1 cursor-pointer">
            <i data-lucide="check-circle" class="w-3.5 h-3.5"></i>
            <span>Approve & Verify Milestone</span>
          </button>
        </div>
      ` : ''}
    </div>
  `;
}

function getPrevCol(col) {
  if (col === "completed") return "faculty_audit";
  if (col === "faculty_audit") return "in_progress";
  if (col === "in_progress") return "backlog";
  return "backlog";
}

function getNextCol(col) {
  if (col === "backlog") return "in_progress";
  if (col === "in_progress") return "faculty_audit";
  if (col === "faculty_audit") return "completed";
  return "completed";
}

async function moveTaskColumn(taskId, newCol) {
  try {
    const res = await fetch(`${API_BASE}/api/tasks/${taskId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ column: newCol })
    });
    if (!res.ok) throw new Error("Could not move task.");
    loadKanbanBoard();
  } catch (err) {
    showToast("Failed to update task position.", "error");
  }
}

async function approveFacultyAuditTask(taskId) {
  try {
    const res = await fetch(`${API_BASE}/api/tasks/${taskId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        column: "completed",
        audit_status: "approved",
        signed_by: state.currentUser.name
      })
    });
    if (!res.ok) throw new Error("Could not approve task.");
    showToast("Milestone verified and signed off by Faculty Mentor!", "success");
    loadKanbanBoard();
  } catch (err) {
    showToast("Approval failed.", "error");
  }
}

function openNewTaskModal() {
  openModal("modal-new-task");
}

async function handleTaskSubmit(e) {
  e.preventDefault();
  const select = document.getElementById("kanban-project-select");
  const projectId = select ? select.value : null;
  if (!projectId) {
    showToast("Please select an active project first.", "error");
    return;
  }

  const title = document.getElementById("task-create-title").value.trim();
  const column = document.getElementById("task-create-col").value;
  const priority = document.getElementById("task-create-priority").value;
  const assignee = document.getElementById("task-create-assignee").value.trim() || state.currentUser.name;
  const due = document.getElementById("task-create-due").value || null;
  const desc = document.getElementById("task-create-desc").value.trim();

  const payload = {
    project_id: projectId,
    title,
    column,
    priority,
    assignee_name: assignee,
    due_date: due,
    description: desc
  };

  try {
    const res = await fetch(`${API_BASE}/api/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Could not create task.");
    closeModal("modal-new-task");
    document.getElementById("form-new-task").reset();
    showToast("New milestone task added to board!", "success");
    loadKanbanBoard();
  } catch (err) {
    showToast("Failed to create task.", "error");
  }
}

// ==========================================
// 3. ORIGINALITY & SIMILARITY CHECKER
// ==========================================
function loadSamplePlagiarism(type) {
  const titleInput = document.getElementById("plag-check-title");
  const abstractInput = document.getElementById("plag-check-abstract");

  if (type === "bad") {
    if (titleInput) titleInput.value = "Smart Agri-Drone for Foliar Leaf Disease Diagnostics";
    if (abstractInput) {
      abstractInput.value = "Autonomous quadcopter drone equipped with high-resolution RGB camera and edge-AI tensor processing to scan agricultural crop leaves for early fungal blight. The system runs lightweight quantized CNN models on Jetson Nano to classify diseases and stream GPS coordinates via LoRa to cloud dashboard for precision pesticide spraying.";
    }
  } else {
    if (titleInput) titleInput.value = "Hydro-Piezoelectric Subsea Tidal Energy Harvester";
    if (abstractInput) {
      abstractInput.value = "Novel bio-inspired oscillating hydrofoil mechanism converting micro-current underwater vortices into clean electrical energy using lead-free PVDF piezoelectric flexible polymer stacks, coupled with an ultra-low frequency rectifier circuit for marine sensor powering.";
    }
  }
}

async function runPlagiarismAudit() {
  const title = document.getElementById("plag-check-title").value.trim();
  const abstract = document.getElementById("plag-check-abstract").value.trim();

  if (!abstract) {
    showToast("Please enter a project abstract or summary to scan.", "error");
    return;
  }

  const btn = document.getElementById("btn-run-plagiarism");
  const origBtnText = btn.innerHTML;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Scanning Nationwide Database...</span>`;
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/plagiarism/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title || "Submitted Research Abstract",
        abstract: abstract,
        student_name: state.currentUser.name
      })
    });

    if (!res.ok) throw new Error("Scanning failed.");
    const report = await res.json();

    const simScore = report.similarity_score !== undefined ? report.similarity_score : (report.max_similarity || 0);
    const originality = Math.max(0, Math.min(100, (100 - simScore))).toFixed(1);

    const scoreDisplay = document.getElementById("plag-score-display");
    const statusBadge = document.getElementById("plag-status-badge");
    const summaryText = document.getElementById("plag-summary-text");
    const highestTitle = document.getElementById("plag-highest-title");
    const simVal = document.getElementById("plag-sim-val");
    const tokensVal = document.getElementById("plag-tokens-val");

    if (scoreDisplay) scoreDisplay.textContent = `${originality}%`;
    if (simVal) simVal.textContent = `${simScore.toFixed(1)}%`;
    if (tokensVal) tokensVal.textContent = report.token_count || abstract.split(/\s+/).length;
    if (highestTitle) highestTitle.textContent = report.most_similar_project_title || "None (Unique)";

    if (originality >= 85) {
      statusBadge.innerHTML = `<span class="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-bold">Passed — Highly Original & Unique</span>`;
      summaryText.textContent = "Your abstract demonstrates high originality. It complies with national academic integrity standards and is eligible for immediate patent review and grant funding.";
    } else if (originality >= 70) {
      statusBadge.innerHTML = `<span class="px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-bold">Moderate Overlap — Review Recommended</span>`;
      summaryText.textContent = "Moderate similarity detected with existing published student projects. Please refine your technical novelty and methodology description before final publication.";
    } else {
      statusBadge.innerHTML = `<span class="px-3 py-1 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-bold">High Overlap Detected</span>`;
      summaryText.textContent = "Significant conceptual and phrasing overlap detected with an existing project in the national database. Please cite existing work or describe your unique differentiation.";
    }

    showToast(`Scan complete: ${originality}% Originality Score`, "success");
    loadPlagiarismAuditLogs();
  } catch (err) {
    showToast(`Originality check failed: ${err.message}`, "error");
  } finally {
    btn.innerHTML = origBtnText;
    btn.disabled = false;
    if (window.lucide) lucide.createIcons();
  }
}

async function loadPlagiarismAuditLogs() {
  try {
    const res = await fetch(`${API_BASE}/api/plagiarism/audits`);
    if (!res.ok) return;
    const logs = await res.json();

    const tbody = document.getElementById("plag-audit-table-body");
    if (!tbody) return;

    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="py-4 px-4 text-center text-slate-500">No originality audit scans recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(l => {
      const orig = (100 - (l.similarity_score || 0)).toFixed(0);
      const color = orig >= 85 ? 'text-emerald-400' : orig >= 70 ? 'text-amber-400' : 'text-rose-400';
      return `
        <tr class="hover:bg-white/[0.02]">
          <td class="py-3 px-4 font-mono text-slate-400">${(l.id || '').substring(0, 8)}</td>
          <td class="py-3 px-4 font-semibold text-white">${l.title || 'Untitled'}</td>
          <td class="py-3 px-4 font-bold ${color}">${orig}% Unique</td>
          <td class="py-3 px-4 text-slate-300">${(l.similarity_score || 0).toFixed(1)}%</td>
          <td class="py-3 px-4">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${orig >= 85 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'}">
              ${orig >= 85 ? 'Passed' : 'Flagged'}
            </span>
          </td>
          <td class="py-3 px-4 text-slate-400">${l.created_at ? new Date(l.created_at).toLocaleDateString() : 'Today'}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error("Could not load audit logs:", err);
  }
}

// ==========================================
// 4A. PROJECT & SOFTWARE IP STORE
// ==========================================
function filterProjectStore(category) {
  state.projectStoreCategory = category;
  document.querySelectorAll(".project-cat-btn").forEach(btn => {
    if ((category === "all" && btn.textContent.includes("All")) || btn.textContent.includes(category)) {
      btn.className = "project-cat-btn px-4 py-2 rounded-xl text-xs font-bold transition-all bg-cyan-600/30 text-cyan-300 border border-cyan-500/40";
    } else {
      btn.className = "project-cat-btn px-4 py-2 rounded-xl text-xs font-semibold transition-all text-slate-400 hover:text-white bg-slate-900 border border-transparent";
    }
  });
  loadProjectStore();
}

async function loadProjectStore() {
  const cat = state.projectStoreCategory;
  const url = cat && cat !== "all"
    ? `${API_BASE}/api/bazaar/items?store_type=software&category=${encodeURIComponent(cat)}`
    : `${API_BASE}/api/bazaar/items?store_type=software`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Could not load software project store items.");
    const items = await res.json();
    state.projectStoreItems = items;
    renderProjectStoreGrid(items);
  } catch (err) {
    showToast("Error loading software project store.", "error");
  }
}

function renderProjectStoreGrid(items) {
  const grid = document.getElementById("project-store-grid");
  if (!grid) return;

  if (items.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full py-12 text-center glass-panel rounded-3xl p-8 border border-white/[0.08]">
        <div class="w-12 h-12 rounded-2xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center mx-auto mb-3">
          <i data-lucide="folder-git-2" class="w-6 h-6"></i>
        </div>
        <h4 class="text-base font-bold text-white font-heading">No Software Projects Available</h4>
        <p class="text-xs text-slate-400 mt-1">List your AI/ML models, algorithms, or full-stack software repos to start receiving license proposals.</p>
        <button onclick="openNewBazaarModal('software')" class="mt-4 btn-glow-primary px-5 py-2.5 rounded-xl text-xs font-bold inline-flex items-center space-x-2">
          <i data-lucide="code-2" class="w-4 h-4"></i>
          <span>List Software IP</span>
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  const role = state.currentUser ? state.currentUser.role : null;

  grid.innerHTML = items.map(item => {
    let stepNum = 1;
    let stepLabel = "Step 1: Available for Licensing";
    let stepColor = "bg-slate-800 text-slate-300 border-slate-700";

    if (item.escrow_status === "locked" || item.escrow_status === "ordered") {
      stepNum = 2;
      stepLabel = "Step 2: Awaiting IP Clearance";
      stepColor = "bg-amber-500/20 text-amber-300 border-amber-500/30";
    } else if (item.escrow_status === "spoc_verified" || item.escrow_status === "shipped") {
      stepNum = 3;
      stepLabel = "Step 3: Transfer & Code Verification";
      stepColor = "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";
    } else if (item.escrow_status === "delivered" || item.escrow_status === "released") {
      stepNum = 4;
      stepLabel = "Step 4: Royalty Disbursed";
      stepColor = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    }

    let actionBtnHtml = "";
    if (stepNum === 1) {
      if (role === "student") {
        actionBtnHtml = `
          <div class="text-center py-2.5 px-3 text-xs font-medium text-slate-400 bg-white/[0.02] rounded-xl border border-white/[0.06]">
            🔒 Commercial Licensing reserved for Industry / Enterprise
          </div>
        `;
      } else {
        actionBtnHtml = `
          <button onclick="handleEscrowClick('${item.id}', 'lock')" class="w-full btn-glow-primary py-2.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 cursor-pointer">
            <i data-lucide="shield-check" class="w-4 h-4"></i>
            <span>License Software IP (Safe Protection)</span>
          </button>
        `;
      }
    } else if (stepNum === 2) {
      if (role === "spoc" || role === "admin" || role === "faculty") {
        actionBtnHtml = `
          <button onclick="handleEscrowClick('${item.id}', 'verify')" class="w-full btn-glow-primary py-2.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 cursor-pointer">
            <i data-lucide="check-circle-2" class="w-4 h-4"></i>
            <span>Audit & Clear IP License (Coordinator)</span>
          </button>
        `;
      } else {
        actionBtnHtml = `
          <div class="text-center py-2 text-xs font-semibold text-amber-400 bg-amber-950/30 rounded-xl border border-amber-500/30">
            ⏳ Awaiting Coordinator IP & Originality Clearance
          </div>
        `;
      }
    } else if (stepNum === 3) {
      if (role === "buyer" || role === "industrialist" || role === "admin") {
        actionBtnHtml = `
          <button onclick="handleEscrowClick('${item.id}', 'confirm_delivery')" class="w-full btn-glow-primary py-2.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 cursor-pointer">
            <i data-lucide="folder-check" class="w-4 h-4"></i>
            <span>Verify Repo & Disburse Royalties</span>
          </button>
        `;
      } else {
        actionBtnHtml = `
          <div class="text-center py-2 text-xs font-semibold text-cyan-400 bg-cyan-950/30 rounded-xl border border-cyan-500/30">
            📦 Codebase Transferred • Licensee validating
          </div>
        `;
      }
    } else {
      actionBtnHtml = `
        <div class="text-center py-2 text-xs font-bold text-emerald-400 bg-emerald-950/30 rounded-xl border border-emerald-500/30">
          ✅ License Granted & Royalty Disbursed
        </div>
      `;
    }

    let specsHtml = "";
    if (item.specs) {
      specsHtml = `
        <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] text-xs font-mono text-slate-300 space-y-1">
          ${item.specs.split('\n').map(s => `<div>• ${s}</div>`).join('')}
        </div>
      `;
    } else if (item.technical_specs) {
      try {
        const parsed = typeof item.technical_specs === "string" ? JSON.parse(item.technical_specs) : item.technical_specs;
        specsHtml = `
          <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] text-xs font-mono text-slate-300 space-y-1">
            ${Object.entries(parsed).map(([k, v]) => `<div><strong class="text-slate-400">${k}:</strong> ${v}</div>`).join('')}
          </div>
        `;
      } catch (e) { }
    }

    return `
      <div class="glass-panel rounded-3xl p-6 border border-white/[0.08] flex flex-col justify-between space-y-4 hover:border-cyan-500/30 transition-all">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
              ${item.category || 'Software IP'}
            </span>
            <div class="text-xl font-black text-cyan-400 font-heading">
              ₹${(item.price_inr || item.price || 0).toLocaleString()}
            </div>
          </div>

          <h3 class="text-lg font-bold text-white font-heading">${item.title}</h3>
          <p class="text-xs text-slate-300 leading-relaxed">${item.description || 'No description provided.'}</p>

          ${specsHtml}
        </div>

        <div class="pt-4 border-t border-white/[0.06] space-y-3">
          <div class="flex items-center justify-between text-xs">
            <span class="text-slate-400">Developer: <strong class="text-slate-200">${item.seller_name || 'Student Team'}</strong> <span class="text-[10px] text-slate-500">(${item.seller_college || 'IIT Bombay'})</span></span>
            <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${stepColor}">
              ${stepLabel}
            </span>
          </div>
          ${actionBtnHtml}
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

// ==========================================
// 4B. HARDWARE & COMPONENT STORE
// ==========================================
function filterHardwareStore(category) {
  state.hardwareStoreCategory = category;
  document.querySelectorAll(".hardware-cat-btn").forEach(btn => {
    if ((category === "all" && btn.textContent.includes("All")) || btn.textContent.includes(category)) {
      btn.className = "hardware-cat-btn px-4 py-2 rounded-xl text-xs font-bold transition-all bg-emerald-600/30 text-emerald-300 border border-emerald-500/40";
    } else {
      btn.className = "hardware-cat-btn px-4 py-2 rounded-xl text-xs font-semibold transition-all text-slate-400 hover:text-white bg-slate-900 border border-transparent";
    }
  });
  loadHardwareStore();
}

async function loadHardwareStore() {
  const cat = state.hardwareStoreCategory;
  const url = cat && cat !== "all"
    ? `${API_BASE}/api/bazaar/items?store_type=hardware&category=${encodeURIComponent(cat)}`
    : `${API_BASE}/api/bazaar/items?store_type=hardware`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Could not load hardware store items.");
    const items = await res.json();
    state.hardwareStoreItems = items;
    renderHardwareStoreGrid(items);
  } catch (err) {
    showToast("Error loading hardware store.", "error");
  }
}

function renderHardwareStoreGrid(items) {
  const grid = document.getElementById("hardware-store-grid");
  if (!grid) return;

  if (items.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full py-12 text-center glass-panel rounded-3xl p-8 border border-white/[0.08]">
        <div class="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mx-auto mb-3">
          <i data-lucide="cpu" class="w-6 h-6"></i>
        </div>
        <h4 class="text-base font-bold text-white font-heading">No Hardware Items Available</h4>
        <p class="text-xs text-slate-400 mt-1">List assembled prototypes, sensors, or surplus lab BOM kits with Safe Buyer Protection.</p>
        <button onclick="openNewBazaarModal('hardware')" class="mt-4 btn-glow-primary px-5 py-2.5 rounded-xl text-xs font-bold inline-flex items-center space-x-2">
          <i data-lucide="tag" class="w-4 h-4"></i>
          <span>List Hardware Item</span>
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  const role = state.currentUser ? state.currentUser.role : null;

  grid.innerHTML = items.map(item => {
    let stepNum = 1;
    let stepLabel = "Step 1: Available for Order";
    let stepColor = "bg-slate-800 text-slate-300 border-slate-700";

    if (item.escrow_status === "locked" || item.escrow_status === "ordered") {
      stepNum = 2;
      stepLabel = "Step 2: Awaiting College Verification";
      stepColor = "bg-amber-500/20 text-amber-300 border-amber-500/30";
    } else if (item.escrow_status === "spoc_verified" || item.escrow_status === "shipped") {
      stepNum = 3;
      stepLabel = "Step 3: Delivered & In Inspection";
      stepColor = "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";
    } else if (item.escrow_status === "delivered" || item.escrow_status === "released") {
      stepNum = 4;
      stepLabel = "Step 4: Completed & Paid";
      stepColor = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    }

    let actionBtnHtml = "";
    if (stepNum === 1) {
      actionBtnHtml = `
        <button onclick="handleEscrowClick('${item.id}', 'lock')" class="w-full btn-glow-primary py-2.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 cursor-pointer">
          <i data-lucide="shopping-cart" class="w-4 h-4"></i>
          <span>Order Now (Safe Protection)</span>
        </button>
      `;
    } else if (stepNum === 2) {
      if (role === "spoc" || role === "admin" || role === "faculty") {
        actionBtnHtml = `
          <button onclick="handleEscrowClick('${item.id}', 'verify')" class="w-full btn-glow-primary py-2.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 cursor-pointer">
            <i data-lucide="shield-check" class="w-4 h-4"></i>
            <span>Verify & Clear Item (Coordinator)</span>
          </button>
        `;
      } else {
        actionBtnHtml = `
          <div class="text-center py-2 text-xs font-semibold text-amber-400 bg-amber-950/30 rounded-xl border border-amber-500/30">
            ⏳ Awaiting College Coordinator Verification
          </div>
        `;
      }
    } else if (stepNum === 3) {
      if (role === "buyer" || role === "industrialist" || role === "student" || role === "admin" || (state.currentUser && state.currentUser.id === item.escrow_buyer_id)) {
        actionBtnHtml = `
          <button onclick="handleEscrowClick('${item.id}', 'confirm_delivery')" class="w-full btn-glow-primary py-2.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 cursor-pointer">
            <i data-lucide="package-check" class="w-4 h-4"></i>
            <span>Confirm Delivery & Release Funds</span>
          </button>
        `;
      } else {
        actionBtnHtml = `
          <div class="text-center py-2 text-xs font-semibold text-cyan-400 bg-cyan-950/30 rounded-xl border border-cyan-500/30">
            📦 Delivered • Buyer testing item
          </div>
        `;
      }
    } else {
      actionBtnHtml = `
        <div class="text-center py-2 text-xs font-bold text-emerald-400 bg-emerald-950/30 rounded-xl border border-emerald-500/30">
          ✅ Transaction Completed Successfully
        </div>
      `;
    }

    let specsHtml = "";
    if (item.specs) {
      specsHtml = `
        <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] text-xs font-mono text-slate-300 space-y-1">
          ${item.specs.split('\n').map(s => `<div>• ${s}</div>`).join('')}
        </div>
      `;
    } else if (item.technical_specs) {
      try {
        const parsed = typeof item.technical_specs === "string" ? JSON.parse(item.technical_specs) : item.technical_specs;
        specsHtml = `
          <div class="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] text-xs font-mono text-slate-300 space-y-1">
            ${Object.entries(parsed).map(([k, v]) => `<div><strong class="text-slate-400">${k}:</strong> ${v}</div>`).join('')}
          </div>
        `;
      } catch (e) { }
    }

    return `
      <div class="glass-panel rounded-3xl p-6 border border-white/[0.08] flex flex-col justify-between space-y-4 hover:border-emerald-500/30 transition-all">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
              ${item.category || 'Hardware'}
            </span>
            <div class="text-xl font-black text-emerald-400 font-heading">
              ₹${(item.price_inr || item.price || 0).toLocaleString()}
            </div>
          </div>

          <h3 class="text-lg font-bold text-white font-heading">${item.title}</h3>
          <p class="text-xs text-slate-300 leading-relaxed">${item.description || 'No description provided.'}</p>

          ${specsHtml}
        </div>

        <div class="pt-4 border-t border-white/[0.06] space-y-3">
          <div class="flex items-center justify-between text-xs">
            <span class="text-slate-400">Seller: <strong class="text-slate-200">${item.seller_name || 'Student Team'}</strong> <span class="text-[10px] text-slate-500">(${item.seller_college || 'NIT Trichy'})</span></span>
            <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${stepColor}">
              ${stepLabel}
            </span>
          </div>
          ${actionBtnHtml}
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

// Backward-compatible delegates
function filterBazaar(category) {
  state.bazaarCategory = category;
  loadHardwareStore();
  loadProjectStore();
}

async function loadBazaar() {
  await Promise.all([loadProjectStore(), loadHardwareStore()]);
}

async function handleEscrowClick(itemId, action) {
  try {
    const isStudent = state.currentUser && state.currentUser.role === "student";
    const isOrderAction = action === "lock" || action === "buy_now" || action === "hold_escrow";

    const payload = {
      action: action,
      actor_id: state.currentUser ? state.currentUser.id : null,
      actor_role: state.currentUser ? state.currentUser.role : null,
      actor_name: state.currentUser ? state.currentUser.name : null,
      actor_college: state.currentUser ? (state.currentUser.college || state.currentUser.collegeCompany || "") : null,
      buyer_id: state.currentUser ? state.currentUser.id : null,
      buyer_name: state.currentUser ? state.currentUser.name : null,
      buyer_company: state.currentUser ? (state.currentUser.college || state.currentUser.collegeCompany || "") : null,
      buyer_college: state.currentUser ? (state.currentUser.college || state.currentUser.collegeCompany || "") : null
    };

    const res = await fetch(`${API_BASE}/api/bazaar/items/${itemId}/escrow`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Action could not be completed.");
    }

    if (isStudent && isOrderAction) {
      showToast("Hardware item ordered under Student Escrow Protection!", "success");
    } else {
      showToast("Buyer protection order status updated!", "success");
    }

    await Promise.all([loadProjectStore(), loadHardwareStore()]);
    if (state.activeTab === "profile") {
      loadUserProfile();
    }
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

function openNewBazaarModal(defaultType = "software") {
  const catSelect = document.getElementById("bazaar-create-cat");
  if (catSelect) {
    if (defaultType === "hardware") {
      catSelect.value = "Assembled Prototypes";
    } else {
      catSelect.value = "Software IP & Commercial License";
    }
  }
  openModal("modal-list-bazaar");
}

async function handleBazaarSubmit(e) {
  e.preventDefault();
  const title = document.getElementById("bazaar-create-title").value.trim();
  const category = document.getElementById("bazaar-create-cat").value;
  const price = parseFloat(document.getElementById("bazaar-create-price").value) || 10000;
  const specs = document.getElementById("bazaar-create-specs").value.trim();
  const desc = document.getElementById("bazaar-create-desc").value.trim();

  const payload = {
    title,
    category,
    price,
    specs,
    description: desc,
    seller_id: state.currentUser ? state.currentUser.id : "usr_student_1",
    seller_name: state.currentUser ? state.currentUser.name : "Student Creator",
    college: state.currentUser ? (state.currentUser.college || "IIT Bombay") : "IIT Bombay"
  };

  try {
    const res = await fetch(`${API_BASE}/api/bazaar/items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Could not list product.");
    closeModal("modal-list-bazaar");
    document.getElementById("form-list-bazaar").reset();
    showToast("Listing published with safe buyer protection!", "success");
    loadProjectStore();
    loadHardwareStore();
  } catch (err) {
    showToast(`Listing failed: ${err.message}`, "error");
  }
}

// ==========================================
// 5. INDUSTRY GRANTS & FUNDING OFFERS
// ==========================================
function openSubmitOfferModal(projectId = null) {
  if (state.projects.length > 0) {
    populateKanbanSelect(state.projects);
  }
  if (projectId) {
    const targetSelect = document.getElementById("offer-target-project");
    if (targetSelect) targetSelect.value = projectId;
  }
  openModal("modal-submit-offer");
}

async function loadIndustrialOffers() {
  try {
    const res = await fetch(`${API_BASE}/api/offers`);
    if (!res.ok) throw new Error("Could not load proposals.");
    const offers = await res.json();
    state.offers = offers;

    const countBadge = document.getElementById("offers-count-badge");
    if (countBadge) countBadge.textContent = `${offers.length} ${offers.length === 1 ? 'Proposal' : 'Proposals'}`;

    renderOffersList(offers);
  } catch (err) {
    showToast("Error loading funding proposals.", "error");
  }
}

function renderOffersList(offers) {
  const container = document.getElementById("offers-list");
  if (!container) return;

  if (offers.length === 0) {
    container.innerHTML = `
      <div class="py-12 text-center glass-panel rounded-3xl p-8 border border-white/[0.08]">
        <h4 class="text-base font-bold text-white font-heading">No Active Funding Proposals Yet</h4>
        <p class="text-xs text-slate-400 mt-1">Submit grant proposals or commercial license offers to student projects.</p>
        <button onclick="openSubmitOfferModal()" class="mt-4 btn-glow-primary px-4 py-2 rounded-xl text-xs font-bold">Submit Proposal</button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  const role = state.currentUser.role;
  const isStudentOrMentor = role === "student" || role === "faculty" || role === "admin";

  container.innerHTML = offers.map(o => {
    let statusBadge = "bg-amber-500/20 text-amber-300 border-amber-500/30";
    if (o.status === "accepted") statusBadge = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    else if (o.status === "rejected") statusBadge = "bg-rose-500/20 text-rose-300 border-rose-500/30";
    else if (o.status === "counter_offered") statusBadge = "bg-cyan-500/20 text-cyan-300 border-cyan-500/30";

    return `
      <div class="glass-panel rounded-3xl p-6 border border-white/[0.08] flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div class="space-y-2 max-w-2xl">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold text-white">${o.buyer_name || 'Enterprise Sponsor'}</span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full border ${statusBadge}">${(o.status || 'Under Review').toUpperCase()}</span>
            <span class="text-xs text-slate-400">• ${o.proposal_type || 'Research Grant'}</span>
          </div>

          <h4 class="text-base font-bold text-white font-heading">
            Target: <span class="text-emerald-400">${o.project_title || 'Student Innovation'}</span>
          </h4>

          <p class="text-xs text-slate-300 leading-relaxed">${o.terms || 'No specific terms provided.'}</p>
        </div>

        <div class="flex flex-col md:items-end space-y-3 shrink-0">
          <div class="text-2xl font-black text-emerald-400 font-heading">
            ₹${(o.amount || 0).toLocaleString()}
          </div>

          ${isStudentOrMentor && (o.status === "pending" || !o.status) ? `
            <div class="flex items-center space-x-2">
              <button onclick="handleOfferDecision('${o.id}', 'accepted')" class="btn-glow-primary px-3.5 py-1.5 rounded-xl text-xs font-bold">
                Accept Deal
              </button>
              <button onclick="promptCounterOffer('${o.id}')" class="btn-glow-secondary px-3.5 py-1.5 rounded-xl text-xs font-bold">
                Counter
              </button>
              <button onclick="handleOfferDecision('${o.id}', 'rejected')" class="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-rose-950/40 text-rose-400 border border-rose-800/50 hover:bg-rose-900/60">
                Decline
              </button>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

async function handleOfferSubmit(e) {
  e.preventDefault();
  const projectSelect = document.getElementById("offer-target-project");
  const projectId = projectSelect.value;
  const projectTitle = projectSelect.options[projectSelect.selectedIndex].text;
  const type = document.getElementById("offer-proposal-type").value;
  const amount = parseFloat(document.getElementById("offer-amount-input").value) || 100000;
  const terms = document.getElementById("offer-terms-input").value.trim();

  const payload = {
    project_id: projectId,
    project_title: projectTitle,
    buyer_id: state.currentUser.id,
    buyer_name: state.currentUser.company || state.currentUser.name,
    proposal_type: type,
    amount,
    terms
  };

  try {
    const res = await fetch(`${API_BASE}/api/offers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Could not submit funding proposal.");
    closeModal("modal-submit-offer");
    document.getElementById("form-submit-offer").reset();
    showToast("Funding proposal submitted to student creator & mentor!", "success");
    loadIndustrialOffers();
  } catch (err) {
    showToast(`Submission failed: ${err.message}`, "error");
  }
}

async function handleOfferDecision(offerId, status) {
  try {
    const res = await fetch(`${API_BASE}/api/offers/${offerId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status })
    });
    if (!res.ok) throw new Error("Could not update proposal.");
    showToast(`Proposal status marked as ${status.toUpperCase()}!`, "success");
    loadIndustrialOffers();
  } catch (err) {
    showToast("Action failed.", "error");
  }
}

async function promptCounterOffer(offerId) {
  const counterAmount = prompt("Enter your proposed counter-offer amount (₹):", "350000");
  if (!counterAmount) return;

  try {
    const res = await fetch(`${API_BASE}/api/offers/${offerId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: "counter_offered",
        amount: parseFloat(counterAmount)
      })
    });
    if (!res.ok) throw new Error("Counter offer failed.");
    showToast(`Counter offer of ₹${parseFloat(counterAmount).toLocaleString()} proposed!`, "success");
    loadIndustrialOffers();
  } catch (err) {
    showToast("Could not send counter offer.", "error");
  }
}

// ==========================================
// 6. VIDEO CONFERENCE & VIRTUAL MEETINGS
// ==========================================
function populateMeetingProjectsSelect(projects) {
  const select = document.getElementById("meeting-create-project");
  if (!select) return;
  select.innerHTML = projects.map(p => `<option value="${p.id}">${p.title}</option>`).join('');
}

async function loadMeetings() {
  try {
    const res = await fetch(`${API_BASE}/api/meetings`);
    if (!res.ok) return;
    const data = await res.json();
    state.meetings = data;

    const countBadge = document.getElementById("meetings-count-badge");
    if (countBadge) countBadge.textContent = `${data.length} Active`;

    renderMeetingsList(data);
  } catch (err) {
    console.error("Could not load meetings:", err);
  }
}

function renderMeetingsList(meetings) {
  const container = document.getElementById("meetings-list");
  if (!container) return;

  if (meetings.length === 0) {
    container.innerHTML = `<div class="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.05] text-center text-xs text-slate-400">No active conference rooms. Start a new session.</div>`;
    return;
  }

  container.innerHTML = meetings.map(m => `
    <div onclick="selectMeetingRoom('${m.id}')" class="glass-panel p-4 rounded-2xl border border-white/[0.08] hover:border-cyan-500/40 transition-all cursor-pointer space-y-2 group">
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
          ${m.meeting_type || 'Collaboration'}
        </span>
        <span class="text-[11px] text-slate-400 font-mono">${m.participants_count || 1} participant(s)</span>
      </div>
      <h4 class="text-xs font-bold text-white group-hover:text-cyan-300 transition-colors line-clamp-1">${m.title}</h4>
      <p class="text-[11px] text-slate-400 truncate">Host: ${m.host_name} • ${m.project_title || 'General'}</p>
    </div>
  `).join('');

  if (window.lucide) lucide.createIcons();
}

function selectMeetingRoom(roomId) {
  const room = state.meetings.find(m => m.id === roomId);
  if (!room) return;

  state.activeMeeting = room;
  document.getElementById("active-meeting-title").textContent = room.title;
  document.getElementById("active-meeting-type").textContent = room.meeting_type || "Video Session";

  const jitsiBtn = document.getElementById("btn-launch-jitsi");
  if (jitsiBtn && room.jitsi_room_url) {
    jitsiBtn.href = room.jitsi_room_url;
  }

  showToast(`Joined Virtual Session: ${room.title}`, "info");
}

function openNewMeetingModal() {
  openModal("modal-new-meeting");
}

async function handleMeetingSubmit(e) {
  e.preventDefault();
  const title = document.getElementById("meeting-create-title").value.trim();
  const meetingType = document.getElementById("meeting-create-type").value;
  const projectSelect = document.getElementById("meeting-create-project");
  const projectId = projectSelect ? projectSelect.value : null;
  const projectTitle = projectSelect && projectSelect.selectedIndex >= 0 ? projectSelect.options[projectSelect.selectedIndex].text : null;

  const payload = {
    title,
    meeting_type: meetingType,
    project_id: projectId,
    project_title: projectTitle,
    host_id: state.currentUser.id,
    host_name: state.currentUser.name
  };

  try {
    const res = await fetch(`${API_BASE}/api/meetings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Could not create meeting room.");
    const created = await res.json();
    closeModal("modal-new-meeting");
    document.getElementById("form-new-meeting").reset();
    showToast(`Virtual Room "${created.title}" created!`, "success");
    await loadMeetings();
    selectMeetingRoom(created.id);
  } catch (err) {
    showToast(`Error creating room: ${err.message}`, "error");
  }
}

function launchMeetingForActiveProject() {
  switchTab("meeting");
  const select = document.getElementById("kanban-project-select");
  const title = select && select.selectedIndex >= 0 ? `${select.options[select.selectedIndex].text} — Mentor Review Call` : "Milestone Review Call";

  document.getElementById("meeting-create-title").value = title;
  openNewMeetingModal();
}

// ==========================================
// 7. 24/7 AI INNOVATION ASSISTANT CHATBOT
// ==========================================
function toggleAIChat() {
  const windowEl = document.getElementById("ai-chat-window");
  if (!windowEl) return;

  state.isAIChatOpen = !state.isAIChatOpen;
  if (state.isAIChatOpen) {
    windowEl.classList.remove("hidden");
    windowEl.classList.add("flex");
    const input = document.getElementById("ai-chat-input");
    if (input) input.focus();
  } else {
    windowEl.classList.add("hidden");
    windowEl.classList.remove("flex");
  }
}

function sendQuickPrompt(promptText) {
  const input = document.getElementById("ai-chat-input");
  if (input) {
    input.value = promptText;
    handleAIChatSubmit(new Event("submit"));
  }
}

async function handleAIChatSubmit(e) {
  if (e && e.preventDefault) e.preventDefault();
  const input = document.getElementById("ai-chat-input");
  const msg = input ? input.value.trim() : "";
  if (!msg) return;

  appendChatMessage("user", msg);
  input.value = "";

  const container = document.getElementById("ai-chat-messages");
  const typingId = "typing-" + Date.now();
  const typingEl = document.createElement("div");
  typingEl.id = typingId;
  typingEl.className = "flex items-start space-x-2";
  typingEl.innerHTML = `
    <div class="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
      <i data-lucide="bot" class="w-3.5 h-3.5"></i>
    </div>
    <div class="p-3 rounded-2xl bg-white/[0.05] border border-white/[0.08] text-slate-400 text-xs italic">
      PRO-VERSED AI is thinking...
    </div>
  `;
  container.appendChild(typingEl);
  container.scrollTop = container.scrollHeight;
  if (window.lucide) lucide.createIcons();

  try {
    const res = await fetch(`${API_BASE}/api/ai/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: msg,
        role: state.currentUser.role,
        name: state.currentUser.name
      })
    });

    const typingNode = document.getElementById(typingId);
    if (typingNode) typingNode.remove();

    if (!res.ok) throw new Error("AI response failed.");
    const data = await res.json();
    appendChatMessage("bot", data.reply);
  } catch (err) {
    const typingNode = document.getElementById(typingId);
    if (typingNode) typingNode.remove();
    appendChatMessage("bot", "⚠️ Sorry, I could not process your request at this moment. Please try again.");
  }
}

function appendChatMessage(sender, text) {
  const container = document.getElementById("ai-chat-messages");
  if (!container) return;

  const msgDiv = document.createElement("div");
  if (sender === "user") {
    msgDiv.className = "flex justify-end";
    msgDiv.innerHTML = `
      <div class="p-3 rounded-2xl bg-emerald-600/30 border border-emerald-500/40 text-emerald-100 max-w-[85%]">
        ${text}
      </div>
    `;
  } else {
    const formatted = text
      .replace(/\n\n/g, '<br/><br/>')
      .replace(/\n/g, '<br/>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>');

    msgDiv.className = "flex items-start space-x-2";
    msgDiv.innerHTML = `
      <div class="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
        <i data-lucide="bot" class="w-3.5 h-3.5"></i>
      </div>
      <div class="p-3 rounded-2xl bg-white/[0.05] border border-white/[0.08] text-slate-200 max-w-[85%]">
        ${formatted}
      </div>
    `;
  }

  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
  if (window.lucide) lucide.createIcons();
}

// ==========================================
// 8. PROFILE DASHBOARD SYSTEM
// ==========================================
async function loadUserProfile() {
  updateUserUI();
  const u = state.currentUser || {
    id: "usr_guest",
    name: "Guest Innovator",
    email: "innovator@proversed.in",
    role: "student",
    college: "IIT Bombay",
    avatar_url: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80"
  };

  // Populate settings form inputs
  const editName = document.getElementById("profile-edit-name");
  const editCollege = document.getElementById("profile-edit-college");
  const editEmail = document.getElementById("profile-edit-email");
  const editGithub = document.getElementById("profile-edit-github");
  const editTech = document.getElementById("profile-edit-tech");
  const editBio = document.getElementById("profile-edit-bio");

  if (editName) editName.value = u.name || "";
  if (editCollege) editCollege.value = u.college || u.company || "";
  if (editEmail) editEmail.value = u.email || "";
  if (editGithub) editGithub.value = u.github || "";
  if (editTech) editTech.value = u.tech_stack || u.skills || "Python, PyTorch, ROS2, ESP32, C++, React";
  if (editBio) editBio.value = u.bio || "Student innovator developing next-generation autonomous hardware and AI systems.";

  // Fetch or retrieve projects & hardware orders
  try {
    if (!state.projects || state.projects.length === 0) {
      const res = await fetch(`${API_BASE}/api/projects`);
      if (res.ok) state.projects = await res.json();
    }
  } catch (e) { }

  let allHardware = [];
  try {
    const resH = await fetch(`${API_BASE}/api/bazaar/items`);
    if (resH.ok) {
      allHardware = await resH.json();
      state.hardwareStoreItems = allHardware;
    }
  } catch (e) { }

  const projects = state.projects || [];
  // Filter user submitted projects
  const myProjects = projects.filter(p =>
    p.student_id === u.id ||
    p.author_id === u.id ||
    p.author === u.name ||
    p.student_name === u.name ||
    p.creator_id === u.id ||
    (p.team && p.team.includes(u.name)) ||
    (p.college && u.college && p.college.toLowerCase() === u.college.toLowerCase())
  );

  // Filter user orders / purchases
  const myOrders = (allHardware || []).filter(item =>
    item.escrow_buyer_id === u.id ||
    item.buyer_id === u.id ||
    item.buyer_name === u.name ||
    item.escrow_buyer_name === u.name ||
    (item.seller_id === u.id) ||
    (item.escrow_status && item.escrow_status !== "available" && item.escrow_status !== "open" && (item.buyer_id === u.id || item.escrow_buyer_id === u.id))
  );

  // Calculate KPIs
  const totalProjects = myProjects.length;
  const activeOrders = myOrders.length;
  const ipfsCount = myProjects.filter(p => p.ipfs_hash || p.blockchain_hash || p.ipfs_cid).length || totalProjects;

  let totalGrants = 0;
  myProjects.forEach(p => {
    if (p.grant_amount || p.funding_inr) {
      totalGrants += Number(p.grant_amount || p.funding_inr || 0);
    }
  });
  if (totalGrants === 0 && totalProjects > 0) {
    totalGrants = totalProjects * 250000;
  }

  // Quick stats
  const qProjects = document.getElementById("profile-quick-projects");
  const qOrders = document.getElementById("profile-quick-orders");
  const qIpfs = document.getElementById("profile-quick-ipfs");
  if (qProjects) qProjects.textContent = totalProjects;
  if (qOrders) qOrders.textContent = activeOrders;
  if (qIpfs) qIpfs.textContent = ipfsCount;

  // KPI cards
  const kpiProjects = document.getElementById("profile-kpi-projects");
  const kpiOrders = document.getElementById("profile-kpi-orders");
  const kpiGrants = document.getElementById("profile-kpi-grants");
  const kpiBadges = document.getElementById("profile-kpi-badges");
  if (kpiProjects) kpiProjects.textContent = totalProjects;
  if (kpiOrders) kpiOrders.textContent = activeOrders;
  if (kpiGrants) kpiGrants.textContent = `₹${totalGrants.toLocaleString()}`;
  if (kpiBadges) kpiBadges.textContent = totalProjects > 0 ? "100%" : "Verified";

  renderProfileProjectsList(myProjects);
  renderProfileOrdersList(myOrders);

  if (window.lucide) lucide.createIcons();
}

function switchProfileSubTab(subTab) {
  const secProjects = document.getElementById("profile-section-projects");
  const secOrders = document.getElementById("profile-section-orders");
  const secSettings = document.getElementById("profile-section-settings");

  const btnProjects = document.getElementById("profile-tab-btn-projects");
  const btnOrders = document.getElementById("profile-tab-btn-orders");
  const btnSettings = document.getElementById("profile-tab-btn-settings");

  if (secProjects) secProjects.classList.toggle("hidden", subTab !== "projects");
  if (secOrders) secOrders.classList.toggle("hidden", subTab !== "orders");
  if (secSettings) secSettings.classList.toggle("hidden", subTab !== "settings");

  const activeClasses = ["bg-emerald-600/30", "text-emerald-300", "border-emerald-500/40", "font-bold"];
  const inactiveClasses = ["text-slate-400", "bg-slate-900/60", "border-transparent", "font-semibold"];

  [
    { btn: btnProjects, isTarget: subTab === "projects" },
    { btn: btnOrders, isTarget: subTab === "orders" },
    { btn: btnSettings, isTarget: subTab === "settings" }
  ].forEach(({ btn, isTarget }) => {
    if (btn) {
      if (isTarget) {
        btn.classList.add(...activeClasses);
        btn.classList.remove(...inactiveClasses);
      } else {
        btn.classList.remove(...activeClasses);
        btn.classList.add(...inactiveClasses);
      }
    }
  });

  if (window.lucide) lucide.createIcons();
}

function saveUserProfile(event) {
  if (event) event.preventDefault();
  const name = document.getElementById("profile-edit-name")?.value.trim();
  const college = document.getElementById("profile-edit-college")?.value.trim();
  const github = document.getElementById("profile-edit-github")?.value.trim();
  const tech = document.getElementById("profile-edit-tech")?.value.trim();
  const bio = document.getElementById("profile-edit-bio")?.value.trim();

  if (!state.currentUser) {
    state.currentUser = { id: "usr_student_aarav", role: "student" };
  }

  if (name) state.currentUser.name = name;
  if (college) {
    state.currentUser.college = college;
    state.currentUser.company = college;
  }
  if (github) state.currentUser.github = github;
  if (tech) state.currentUser.tech_stack = tech;
  if (bio) state.currentUser.bio = bio;

  try {
    localStorage.setItem("proversed_user", JSON.stringify(state.currentUser));
  } catch (e) { }

  updateUserUI();
  loadUserProfile();
  showToast("Profile settings saved successfully!", "success");
}

function renderProfileProjectsList(projects) {
  const container = document.getElementById("profile-projects-list");
  if (!container) return;

  if (!projects || projects.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-12 text-center glass-panel rounded-3xl p-8 border border-white/[0.08]">
        <div class="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mx-auto mb-3">
          <i data-lucide="folder-plus" class="w-6 h-6"></i>
        </div>
        <h4 class="text-base font-bold text-white font-heading">No Projects Submitted Yet</h4>
        <p class="text-xs text-slate-400 mt-1">Register your academic innovations, hardware prototypes, or capstone projects to receive grants and verification.</p>
        <button onclick="openNewProjectModal()" class="mt-4 btn-glow-primary px-5 py-2.5 rounded-xl text-xs font-bold inline-flex items-center space-x-2 cursor-pointer">
          <i data-lucide="plus-circle" class="w-4 h-4"></i>
          <span>+ Submit New Project</span>
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = projects.map(p => {
    const origScore = p.originality_score || p.originality || 94;
    const stage = p.status || p.stage || "Prototype Ready";
    const ipfsHash = p.ipfs_hash || p.blockchain_hash || `QmX${Math.random().toString(36).substring(2, 10)}...`;

    return `
      <div class="glass-panel rounded-3xl p-6 border border-white/[0.08] flex flex-col justify-between space-y-4 hover:border-emerald-500/30 transition-all group">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
              ${p.domain || p.category || 'DeepTech & AI'}
            </span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
              ${stage}
            </span>
          </div>

          <h4 class="text-base font-bold text-white font-heading group-hover:text-emerald-400 transition-colors">${p.title}</h4>
          <p class="text-xs text-slate-300 line-clamp-2 leading-relaxed">${p.description || 'No project description provided.'}</p>
        </div>

        <div class="pt-4 border-t border-white/[0.06] space-y-3 text-xs">
          <div class="flex items-center justify-between text-slate-400">
            <span class="flex items-center space-x-1">
              <i data-lucide="shield-check" class="w-3.5 h-3.5 text-emerald-400"></i>
              <span>Originality: <strong class="text-emerald-300">${origScore}%</strong></span>
            </span>
            <span class="font-mono text-[10px] text-cyan-400 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-500/30">
              IPFS: ${ipfsHash.substring(0, 10)}...
            </span>
          </div>

          <div class="flex items-center gap-2 pt-1">
            <button onclick="openProjectDetailsModal('${p.id}')" class="flex-1 py-2 rounded-xl text-xs font-semibold bg-white/5 hover:bg-white/10 text-slate-200 hover:text-white border border-white/10 transition-colors text-center cursor-pointer">
              View Project
            </button>
            <button onclick="switchTab('kanban')" class="px-3 py-2 rounded-xl text-xs font-semibold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 transition-colors cursor-pointer" title="Open in Task Board">
              <i data-lucide="kanban" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

function renderProfileOrdersList(orders) {
  const container = document.getElementById("profile-orders-list");
  if (!container) return;

  if (!orders || orders.length === 0) {
    container.innerHTML = `
      <div class="py-12 text-center glass-panel rounded-3xl p-8 border border-white/[0.08]">
        <div class="w-12 h-12 rounded-2xl bg-amber-500/10 text-amber-400 flex items-center justify-center mx-auto mb-3">
          <i data-lucide="shopping-bag" class="w-6 h-6"></i>
        </div>
        <h4 class="text-base font-bold text-white font-heading">No Active Hardware Orders</h4>
        <p class="text-xs text-slate-400 mt-1">You haven't ordered any hardware prototypes or kits under Safe Escrow Protection yet.</p>
        <button onclick="switchTab('hardwareStore')" class="mt-4 btn-glow-primary px-5 py-2.5 rounded-xl text-xs font-bold inline-flex items-center space-x-2 cursor-pointer">
          <i data-lucide="cpu" class="w-4 h-4"></i>
          <span>Browse Hardware Store</span>
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = orders.map(item => {
    let stepNum = 1;
    let step1Class = "bg-emerald-500 text-slate-950 font-bold ring-2 ring-emerald-400/50";
    let step2Class = "bg-slate-800 text-slate-400 border border-white/10";
    let step3Class = "bg-slate-800 text-slate-400 border border-white/10";
    let step4Class = "bg-slate-800 text-slate-400 border border-white/10";

    if (item.escrow_status === "locked" || item.escrow_status === "ordered") {
      stepNum = 2;
      step2Class = "bg-amber-500 text-slate-950 font-bold ring-2 ring-amber-400/50";
    } else if (item.escrow_status === "spoc_verified" || item.escrow_status === "shipped") {
      stepNum = 3;
      step2Class = "bg-emerald-500 text-slate-950 font-bold";
      step3Class = "bg-cyan-500 text-slate-950 font-bold ring-2 ring-cyan-400/50";
    } else if (item.escrow_status === "delivered" || item.escrow_status === "released" || item.escrow_status === "completed") {
      stepNum = 4;
      step2Class = "bg-emerald-500 text-slate-950 font-bold";
      step3Class = "bg-emerald-500 text-slate-950 font-bold";
      step4Class = "bg-emerald-500 text-slate-950 font-bold ring-2 ring-emerald-400/50";
    }

    let actionHtml = "";
    if (stepNum === 3) {
      actionHtml = `
        <button onclick="handleEscrowClick('${item.id}', 'confirm_delivery')" class="btn-glow-primary px-4 py-2 rounded-xl text-xs font-bold flex items-center space-x-1.5 cursor-pointer">
          <i data-lucide="package-check" class="w-4 h-4"></i>
          <span>Confirm Delivery & Release Payout</span>
        </button>
      `;
    } else if (stepNum === 4) {
      actionHtml = `
        <div class="px-3 py-1.5 rounded-xl bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-bold flex items-center space-x-1">
          <i data-lucide="check-circle" class="w-3.5 h-3.5"></i>
          <span>Funds Released to Seller</span>
        </div>
      `;
    } else if (stepNum === 2) {
      actionHtml = `
        <div class="px-3 py-1.5 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-bold flex items-center space-x-1">
          <i data-lucide="clock" class="w-3.5 h-3.5"></i>
          <span>Awaiting Coordinator Verification</span>
        </div>
      `;
    } else {
      actionHtml = `
        <div class="px-3 py-1.5 rounded-xl bg-slate-800 text-slate-300 border border-white/10 text-xs font-medium">
          Order Placed
        </div>
      `;
    }

    return `
      <div class="glass-panel p-6 rounded-3xl border border-white/[0.08] space-y-5 hover:border-emerald-500/30 transition-all">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div class="flex items-center space-x-2">
              <span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                ${item.category || 'Hardware Prototype'}
              </span>
              <span class="text-xs text-slate-400">Order ID: <strong class="font-mono text-slate-200">#ESC-${item.id.substring(0, 8)}</strong></span>
            </div>
            <h4 class="text-lg font-bold text-white font-heading mt-1">${item.title}</h4>
            <p class="text-xs text-slate-400">Seller: <strong class="text-slate-200">${item.seller_name || 'Student Creator'}</strong> (${item.seller_college || 'Academic Lab'})</p>
          </div>

          <div class="flex flex-col sm:items-end gap-2">
            <div class="text-2xl font-black text-emerald-400 font-heading">₹${(item.price_inr || item.price || 0).toLocaleString()}</div>
            ${actionHtml}
          </div>
        </div>

        <!-- 4-Step Escrow Stepper -->
        <div class="pt-4 border-t border-white/[0.06]">
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div class="flex items-center space-x-2.5 p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.05]">
              <div class="w-6 h-6 rounded-full flex items-center justify-center text-[10px] shrink-0 ${step1Class}">1</div>
              <div>
                <div class="text-xs font-bold text-white">Order Placed</div>
                <div class="text-[10px] text-slate-400">Escrow Locked</div>
              </div>
            </div>

            <div class="flex items-center space-x-2.5 p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.05]">
              <div class="w-6 h-6 rounded-full flex items-center justify-center text-[10px] shrink-0 ${step2Class}">2</div>
              <div>
                <div class="text-xs font-bold text-white">College Verified</div>
                <div class="text-[10px] text-slate-400">Lab Approved</div>
              </div>
            </div>

            <div class="flex items-center space-x-2.5 p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.05]">
              <div class="w-6 h-6 rounded-full flex items-center justify-center text-[10px] shrink-0 ${step3Class}">3</div>
              <div>
                <div class="text-xs font-bold text-white">Delivered</div>
                <div class="text-[10px] text-slate-400">Inspection Active</div>
              </div>
            </div>

            <div class="flex items-center space-x-2.5 p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.05]">
              <div class="w-6 h-6 rounded-full flex items-center justify-center text-[10px] shrink-0 ${step4Class}">4</div>
              <div>
                <div class="text-xs font-bold text-white">Funds Released</div>
                <div class="text-[10px] text-slate-400">Payout Complete</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

function updateAnalyticsDashboardUI() {
  updateUserUI();
  loadUserProfile();
}


window.addEventListener("resize", () => {
  if (state.activeTab === "analytics" || state.activeTab === "dashboard") {
    if (state.charts) {
      Object.values(state.charts).forEach(c => {
        if (c && typeof c.resize === "function") {
          try { c.resize(); } catch (e) { }
        }
      });
    }
  }
});

function safeDestroyChart(chartKey, canvas) {
  if (typeof Chart === "undefined") return;
  if (state.charts && state.charts[chartKey]) {
    try {
      state.charts[chartKey].destroy();
    } catch (e) { }
    state.charts[chartKey] = null;
  }
  if (canvas) {
    try {
      const existing = Chart.getChart(canvas);
      if (existing) existing.destroy();
    } catch (e) { }
  }
}

function extractChartLabelsAndData(input, defaultLabels, defaultData) {
  if (!input) return { labels: defaultLabels, data: defaultData };
  if (Array.isArray(input.labels) && Array.isArray(input.data)) {
    return { labels: input.labels, data: input.data };
  }
  if (typeof input === "object" && Object.keys(input).length > 0) {
    return { labels: Object.keys(input), data: Object.values(input) };
  }
  return { labels: defaultLabels, data: defaultData };
}

async function loadNationalAnalytics() {
  const demoTech = {
    labels: ['Python', 'PyTorch', 'ROS2', 'C++', 'TensorFlow', 'STM32', 'React/Node'],
    data: [142, 98, 64, 88, 56, 72, 115]
  };
  const demoLifecycle = {
    labels: ['Ideation', 'In Development', 'Prototype Ready', 'Completed', 'Research Published'],
    data: [110, 180, 140, 80, 30]
  };
  const demoDomains = {
    labels: ['AI & Robotics', 'Green Tech & Energy', 'Healthcare & MedTech', 'Smart Cities & IoT', 'FinTech & Security', 'Aerospace'],
    data: [180, 120, 90, 85, 40, 25]
  };
  const demoCompliance = {
    labels: ['90-100% Unique', '80-89% Unique', '70-79% Unique', '<70% Flagged'],
    data: [380, 110, 35, 15]
  };

  // Always render demo graphs immediately so canvases are never blank
  renderTechStackChart(demoTech);
  renderLifecycleChart(demoLifecycle);
  renderDomainChart(demoDomains);
  renderComplianceChart(demoCompliance);

  try {
    const res = await fetch(`${API_BASE}/api/analytics/national`);
    if (!res.ok) throw new Error("Could not fetch analytics.");
    const data = await res.json();
    state.analytics = data;

    if (data.summary) {
      const totProjects = document.getElementById("dash-metric-projects") || document.getElementById("metric-total-projects");
      const totFunding = document.getElementById("dash-metric-dealflow") || document.getElementById("metric-total-dealflow");
      const totProto = document.getElementById("dash-metric-prototypes") || document.getElementById("metric-prototypes-ready");
      const totInst = document.getElementById("dash-metric-institutions") || document.getElementById("metric-institutions");

      if (totProjects) totProjects.textContent = data.summary.total_national_projects ? `${data.summary.total_national_projects}+` : "540+";
      if (totFunding) totFunding.textContent = data.summary.total_ip_dealflow_inr ? `₹${data.summary.total_ip_dealflow_inr.toLocaleString()}` : "₹48,50,000";
      if (totProto) totProto.textContent = data.summary.prototypes_ready ? `${data.summary.prototypes_ready}` : "186";
      if (totInst) totInst.textContent = data.summary.participating_institutions ? `${data.summary.participating_institutions}+` : "45+";
    }

    if (data.top_tech_stacks && Object.keys(data.top_tech_stacks).length >= 4) {
      renderTechStackChart({ labels: Object.keys(data.top_tech_stacks), data: Object.values(data.top_tech_stacks) });
    }
    if (data.lifecycle_funnel && Object.keys(data.lifecycle_funnel).length >= 3) {
      renderLifecycleChart({ labels: Object.keys(data.lifecycle_funnel), data: Object.values(data.lifecycle_funnel) });
    }
    if (data.domain_distribution && Object.keys(data.domain_distribution).length >= 3) {
      renderDomainChart({ labels: Object.keys(data.domain_distribution), data: Object.values(data.domain_distribution) });
    }
    if (data.plagiarism_compliance && Object.keys(data.plagiarism_compliance).length >= 3) {
      renderComplianceChart({ labels: Object.keys(data.plagiarism_compliance), data: Object.values(data.plagiarism_compliance) });
    }
  } catch (err) {
    console.warn("Using default demo graphs for analytics dashboard:", err);
    renderTechStackChart(demoTech);
    renderLifecycleChart(demoLifecycle);
    renderDomainChart(demoDomains);
    renderComplianceChart(demoCompliance);
  }
}

function renderTechStackChart(data) {
  const canvas = document.getElementById("chart-tech-stack");
  if (!canvas) return;
  if (typeof Chart === "undefined") {
    setTimeout(() => renderTechStackChart(data), 100);
    return;
  }

  safeDestroyChart("techStack", canvas);

  const defaultLabels = ['Python', 'PyTorch', 'ROS2', 'C++', 'TensorFlow', 'STM32', 'React/Node'];
  const defaultData = [142, 98, 64, 88, 56, 72, 115];
  const { labels, data: values } = extractChartLabelsAndData(data, defaultLabels, defaultData);

  const ctx = canvas.getContext('2d');
  state.charts.techStack = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Projects Using Tech',
        data: values,
        backgroundColor: 'rgba(16, 185, 129, 0.75)',
        borderColor: '#10b981',
        borderWidth: 1.5,
        borderRadius: 8,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#f1f5f9',
          bodyColor: '#10b981',
          borderColor: 'rgba(16, 185, 129, 0.3)',
          borderWidth: 1,
          padding: 10,
          displayColors: false
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
        }
      }
    }
  });
}

function renderLifecycleChart(data) {
  const canvas = document.getElementById("chart-lifecycle");
  if (!canvas) return;
  if (typeof Chart === "undefined") {
    setTimeout(() => renderLifecycleChart(data), 100);
    return;
  }

  safeDestroyChart("lifecycle", canvas);

  const defaultLabels = ['Ideation', 'In Development', 'Prototype Ready', 'Completed', 'Research Published'];
  const defaultData = [110, 180, 140, 80, 30];
  const { labels, data: values } = extractChartLabelsAndData(data, defaultLabels, defaultData);

  const ctx = canvas.getContext('2d');
  const colors = ['#64748b', '#6366f1', '#06b6d4', '#10b981', '#f59e0b'];

  state.charts.lifecycle = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: '#0f172a',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '70%',
      plugins: {
        legend: {
          position: 'right',
          labels: {
            color: '#cbd5e1',
            font: { family: 'Inter', size: 11 },
            boxWidth: 12,
            padding: 12
          }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#f1f5f9',
          bodyColor: '#06b6d4',
          borderColor: 'rgba(6, 182, 212, 0.3)',
          borderWidth: 1,
          padding: 10
        }
      }
    }
  });
}

function renderDomainChart(data) {
  const canvas = document.getElementById("chart-domains");
  if (!canvas) return;
  if (typeof Chart === "undefined") {
    setTimeout(() => renderDomainChart(data), 100);
    return;
  }

  safeDestroyChart("domains", canvas);

  const defaultLabels = ['AI & Robotics', 'Green Tech & Energy', 'Healthcare & MedTech', 'Smart Cities & IoT', 'FinTech & Security', 'Aerospace'];
  const defaultData = [180, 120, 90, 85, 40, 25];
  const { labels, data: values } = extractChartLabelsAndData(data, defaultLabels, defaultData);

  const ctx = canvas.getContext('2d');
  const colors = ['#10b981', '#06b6d4', '#8b5cf6', '#ec4899', '#f59e0b', '#3b82f6'];

  state.charts.domains = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: '#0f172a',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: {
          position: 'right',
          labels: {
            color: '#cbd5e1',
            font: { family: 'Inter', size: 11 },
            boxWidth: 12,
            padding: 10
          }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#f1f5f9',
          bodyColor: '#8b5cf6',
          borderColor: 'rgba(139, 92, 246, 0.3)',
          borderWidth: 1,
          padding: 10
        }
      }
    }
  });
}

function renderComplianceChart(data) {
  const canvas = document.getElementById("chart-compliance");
  if (!canvas) return;
  if (typeof Chart === "undefined") {
    setTimeout(() => renderComplianceChart(data), 100);
    return;
  }

  safeDestroyChart("compliance", canvas);

  const defaultLabels = ['90-100% Unique', '80-89% Unique', '70-79% Unique', '<70% Flagged'];
  const defaultData = [380, 110, 35, 15];
  const { labels, data: values } = extractChartLabelsAndData(data, defaultLabels, defaultData);

  const ctx = canvas.getContext('2d');
  const colors = ['#10b981', '#34d399', '#f59e0b', '#ef4444'];

  state.charts.compliance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Projects',
        data: values,
        backgroundColor: colors,
        borderColor: colors,
        borderWidth: 1,
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#f1f5f9',
          bodyColor: '#34d399',
          borderColor: 'rgba(52, 211, 153, 0.3)',
          borderWidth: 1,
          padding: 10,
          displayColors: false
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
        }
      }
    }
  });
}

// ==========================================
// MODALS & TOAST NOTIFICATION UTILITIES
// ==========================================
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("hidden");
    modal.classList.add("flex");
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
}

window.addEventListener("click", (e) => {
  if (e.target.classList.contains("fixed") && e.target.classList.contains("inset-0")) {
    e.target.classList.add("hidden");
    e.target.classList.remove("flex");
  }
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".fixed.inset-0.flex").forEach(modal => {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    });
  }
});

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  let bg = "bg-slate-900 border-white/[0.1] text-white";
  let icon = "info";

  if (type === "success") {
    bg = "bg-emerald-950/90 border-emerald-500/40 text-emerald-200";
    icon = "check-circle";
  } else if (type === "error") {
    bg = "bg-rose-950/90 border-rose-500/40 text-rose-200";
    icon = "alert-triangle";
  }

  toast.className = `pointer-events-auto flex items-center space-x-3 px-4 py-3 rounded-2xl border ${bg} shadow-2xl backdrop-blur-xl toast-item max-w-md`;
  toast.innerHTML = `
    <i data-lucide="${icon}" class="w-5 h-5 shrink-0"></i>
    <span class="text-xs font-semibold leading-snug">${message}</span>
  `;

  container.appendChild(toast);
  if (window.lucide) lucide.createIcons();

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(-100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function openForgotPasswordModal() {
  const loginEmail = document.getElementById("login-email")?.value.trim() || "";
  const forgotInput = document.getElementById("forgot-email-input");
  if (forgotInput && loginEmail) {
    forgotInput.value = loginEmail;
  }
  openModal("modal-forgot-password");
}

async function handleForgotPasswordSubmit(event) {
  event.preventDefault();
  const emailInput = document.getElementById("forgot-email-input");
  const email = emailInput ? emailInput.value.trim() : "";
  const submitBtn = event.target ? event.target.querySelector("button[type='submit']") : null;
  const originalBtnHtml = submitBtn ? submitBtn.innerHTML : "";

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Sending...</span>`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });

    const data = await res.json().catch(() => ({}));

    if (res.status === 429) {
      showToast(data.detail || "Rate limit exceeded. Please wait before retrying.", "error");
      return;
    }

    closeModal("modal-forgot-password");
    showToast(data.message || `Password recovery instructions dispatched to ${email || 'your email'}.`, "success");
  } catch (err) {
    closeModal("modal-forgot-password");
    showToast("Network error while requesting password reset.", "error");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnHtml;
      if (window.lucide) lucide.createIcons();
    }
  }
}

function openResetPasswordModal(token) {
  const tokenInput = document.getElementById("reset-token-input");
  if (tokenInput && token) {
    tokenInput.value = token;
  }
  openModal("modal-set-new-password");
}

async function handleResetPasswordSubmit(event) {
  event.preventDefault();
  const tokenInput = document.getElementById("reset-token-input");
  const newPasswordInput = document.getElementById("reset-new-password");
  const token = tokenInput ? tokenInput.value.trim() : "";
  const newPassword = newPasswordInput ? newPasswordInput.value : "";
  const submitBtn = event.target ? event.target.querySelector("button[type='submit']") : null;
  const originalBtnHtml = submitBtn ? submitBtn.innerHTML : "";

  if (!token) {
    showToast("Missing password reset token. Please request a new recovery link.", "error");
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Updating...</span>`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, newPassword })
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      showToast(data.detail || "Failed to reset password. Token may be expired or invalid.", "error");
      return;
    }

    closeModal("modal-set-new-password");
    showToast(data.message || "Password successfully reset! Please sign in.", "success");
    if (newPasswordInput) newPasswordInput.value = "";
    if (tokenInput) tokenInput.value = "";
    switchTab("login", false);
  } catch (err) {
    showToast("Network error while resetting password.", "error");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnHtml;
      if (window.lucide) lucide.createIcons();
    }
  }
}


