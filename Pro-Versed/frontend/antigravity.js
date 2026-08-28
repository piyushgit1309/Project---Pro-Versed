/**
 * PRO-VERSED — Google Anti-Gravity Interactive Physics Engine
 * Powered by Matter.js (2D Rigid-Body Simulation, Mouse Momentum & Spring Restoration)
 */

(function (window) {
  "use strict";

  class AntiGravityEngine {
    constructor() {
      this.isActive = false;
      this.isRestoring = false;
      this.engine = null;
      this.runner = null;
      this.renderCanvas = null;
      this.mouseConstraint = null;
      this.physicsItems = [];
      this.boundaries = [];
      this.hudElement = null;
      this.animationFrameId = null;

      this.init();
    }

    init() {
      // Expose globally for trigger button & console access
      window.triggerAntiGravity = () => this.toggle();
      window.restoreAntiGravity = () => this.restore();
      window.setAntiGravityMode = (mode) => this.setGravityMode(mode);

      // Add keyboard shortcut: Ctrl+Shift+G or Alt+G to toggle
      document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "g") || (e.altKey && e.key.toLowerCase() === "g")) {
          e.preventDefault();
          this.toggle();
        }
      });
    }

    toggle() {
      if (this.isActive) {
        this.restore();
      } else {
        this.start();
      }
    }

    start() {
      if (this.isActive || this.isRestoring) return;
      if (typeof Matter === "undefined") {
        console.error("Matter.js is required for Anti-Gravity mode.");
        return;
      }

      this.isActive = true;

      // Matter.js Module Aliases
      const { Engine, Bodies, Body, Composite, Mouse, MouseConstraint, Runner } = Matter;

      // 1. Create Physics Engine
      this.engine = Engine.create({
        gravity: { x: 0, y: 1.0, scale: 0.001 }
      });

      // 2. Select target navigation elements and visible UI cards to collapse
      const targetSelectors = [
        "#ag-brand-icon",
        "#ag-brand-text",
        "#ag-brand-badge",
        "#ag-brand-subtext",
        "#nav-btn-explore",
        "#nav-btn-kanban",
        "#nav-more-dropdown-container",
        "#user-profile-dropdown-container",
        "#nav-cta-btn",
        "#nav-antigravity-btn",
        "#nav-hamburger-btn"
      ];

      const elementsToDrop = [];
      targetSelectors.forEach(sel => {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null) { // Visible elements only
          elementsToDrop.push(el);
        }
      });

      // Also grab visible project cards in viewport (up to 6)
      const projectCards = document.querySelectorAll(".project-card, .task-card");
      let cardCount = 0;
      projectCards.forEach(card => {
        if (cardCount < 6 && card.offsetParent !== null) {
          const r = card.getBoundingClientRect();
          if (r.top < window.innerHeight && r.bottom > 0) {
            elementsToDrop.push(card);
            cardCount++;
          }
        }
      });

      // If specific sub-elements not found, fallback to top-level navbar children
      if (elementsToDrop.length === 0) {
        const header = document.querySelector("header");
        if (header) {
          const children = header.querySelectorAll("button, a, .group, nav");
          children.forEach(el => elementsToDrop.push(el));
        }
      }

      // Close open dropdowns before collapsing
      if (typeof closeMoreDropdown === "function") closeMoreDropdown();
      if (typeof toggleUserDropdown === "function") toggleUserDropdown(false);
      if (typeof toggleMobileDrawer === "function") toggleMobileDrawer(false);

      // 3. Measure bounding boxes & Detach DOM elements into Fixed Coordinates
      this.physicsItems = [];

      elementsToDrop.forEach((el, index) => {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        // Cache original styling & geometry
        const originalStyle = {
          position: el.style.position || "",
          top: el.style.top || "",
          left: el.style.left || "",
          width: el.style.width || "",
          height: el.style.height || "",
          margin: el.style.margin || "",
          transform: el.style.transform || "",
          zIndex: el.style.zIndex || "",
          transition: el.style.transition || "",
          boxShadow: el.style.boxShadow || "",
          cursor: el.style.cursor || ""
        };

        // Switch element to fixed physics layout
        el.style.position = "fixed";
        el.style.left = "0px";
        el.style.top = "0px";
        el.style.width = `${rect.width}px`;
        el.style.height = `${rect.height}px`;
        el.style.margin = "0px";
        el.style.zIndex = "9990";
        el.style.transition = "none";
        el.style.userSelect = "none";
        el.style.cursor = "grab";
        el.style.transformOrigin = "center center";
        el.style.boxShadow = "0 10px 30px rgba(0,0,0,0.6)";

        // Set initial transform
        el.style.transform = `translate3d(${rect.left}px, ${rect.top}px, 0px) rotate(0deg)`;

        // Create Matter.js Dynamic Rigid Body matching the DOM element dimensions
        const body = Bodies.rectangle(
          rect.left + rect.width / 2,
          rect.top + rect.height / 2,
          rect.width,
          rect.height,
          {
            restitution: 0.75 + (Math.random() * 0.15), // Bounciness
            friction: 0.12,                            // Surface sliding friction
            frictionAir: 0.012,                        // Air resistance
            density: 0.002,
            chamfer: { radius: 6 }
          }
        );

        // Impart random initial velocity and angular momentum for realistic tumbling
        Body.setAngularVelocity(body, (Math.random() - 0.5) * 0.18);
        Body.setVelocity(body, {
          x: (Math.random() - 0.5) * 4,
          y: Math.random() * 2 + (index * 0.3)
        });

        Composite.add(this.engine.world, body);

        this.physicsItems.push({
          element: el,
          body: body,
          initialRect: rect,
          originalStyle: originalStyle
        });
      });

      // 4. Create Viewport Boundary Walls (Floor, Left, Right, Ceiling)
      this.createBoundaries();

      // 5. Setup Interactive Mouse Drag & Throw Physics
      this.setupMouseInteraction();

      // 6. Start Physics Runner & Render Loop
      this.runner = Runner.create();
      Runner.run(this.runner, this.engine);

      this.startRenderLoop();

      // 7. Inject Floating HUD Controller (Zero-G, Gravity Controls & Restore Button)
      this.createFloatingHUD();

      // Handle window resizing
      this.onResizeHandler = () => this.createBoundaries();
      window.addEventListener("resize", this.onResizeHandler);

      // Play feedback toast
      if (typeof showToast === "function") {
        showToast("⚡ Anti-Gravity Activated! Drag and throw navbar pieces across the screen.", "info");
      }
    }

    createBoundaries() {
      if (!this.engine) return;
      const { Bodies, Composite } = Matter;

      // Remove existing boundaries if any
      if (this.boundaries.length > 0) {
        this.boundaries.forEach(b => Composite.remove(this.engine.world, b));
        this.boundaries = [];
      }

      const w = window.innerWidth;
      const h = window.innerHeight;
      const thickness = 100;

      // Floor (bottom of window)
      const ground = Bodies.rectangle(w / 2, h + thickness / 2, w * 3, thickness, {
        isStatic: true,
        restitution: 0.8,
        friction: 0.2
      });

      // Left wall
      const leftWall = Bodies.rectangle(-thickness / 2, h / 2, thickness, h * 3, {
        isStatic: true,
        restitution: 0.8,
        friction: 0.1
      });

      // Right wall
      const rightWall = Bodies.rectangle(w + thickness / 2, h / 2, thickness, h * 3, {
        isStatic: true,
        restitution: 0.8,
        friction: 0.1
      });

      // Top ceiling
      const ceiling = Bodies.rectangle(w / 2, -thickness * 2, w * 3, thickness, {
        isStatic: true,
        restitution: 0.8,
        friction: 0.1
      });

      this.boundaries = [ground, leftWall, rightWall, ceiling];
      Composite.add(this.engine.world, this.boundaries);
    }

    setupMouseInteraction() {
      const { Mouse, MouseConstraint, Composite } = Matter;

      // Create mouse instance attached to document
      const mouse = Mouse.create(document.body);
      
      this.mouseConstraint = MouseConstraint.create(this.engine, {
        mouse: mouse,
        constraint: {
          stiffness: 0.25,
          damping: 0.1,
          render: { visible: false }
        }
      });

      Composite.add(this.engine.world, this.mouseConstraint);

      // Update active cursor styling while dragging
      Matter.Events.on(this.mouseConstraint, "startdrag", (e) => {
        const item = this.physicsItems.find(it => it.body === e.body);
        if (item) {
          item.element.style.cursor = "grabbing";
          item.element.style.zIndex = "9999";
        }
      });

      Matter.Events.on(this.mouseConstraint, "enddrag", (e) => {
        const item = this.physicsItems.find(it => it.body === e.body);
        if (item) {
          item.element.style.cursor = "grab";
          item.element.style.zIndex = "9990";
        }
      });
    }

    startRenderLoop() {
      const render = () => {
        if (!this.isActive) return;

        // Synchronize DOM elements with Matter.js physics bodies
        for (let i = 0; i < this.physicsItems.length; i++) {
          const item = this.physicsItems[i];
          const pos = item.body.position;
          const angle = item.body.angle;
          const w = item.initialRect.width;
          const h = item.initialRect.height;

          // translate3d to centered coordinate
          const x = pos.x - w / 2;
          const y = pos.y - h / 2;

          item.element.style.transform = `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, 0px) rotate(${angle.toFixed(4)}rad)`;
        }

        this.animationFrameId = requestAnimationFrame(render);
      };

      this.animationFrameId = requestAnimationFrame(render);
    }

    createFloatingHUD() {
      if (this.hudElement) this.hudElement.remove();

      const hud = document.createElement("div");
      hud.id = "antigravity-floating-hud";
      hud.className = "fixed top-5 right-5 z-[10000] flex flex-col items-end space-y-2 pointer-events-auto modal-enter";
      hud.innerHTML = `
        <div class="glass-panel p-3 sm:p-4 rounded-2xl border border-purple-500/40 bg-slate-950/90 shadow-2xl backdrop-blur-2xl flex items-center space-x-3">
          <div class="flex items-center space-x-2">
            <span class="w-2.5 h-2.5 rounded-full bg-purple-400 animate-ping"></span>
            <span class="text-xs font-bold text-white font-heading">Anti-Gravity Physics Active</span>
          </div>

          <div class="flex items-center space-x-1.5 pl-2 border-l border-white/10">
            <button onclick="setAntiGravityMode('normal')" title="Earth Gravity (1.0g)" class="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white text-xs transition-colors cursor-pointer">
              ⬇️ 1G
            </button>
            <button onclick="setAntiGravityMode('zero')" title="Zero-Gravity (Float)" class="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white text-xs transition-colors cursor-pointer">
              🌌 Zero-G
            </button>
            <button onclick="setAntiGravityMode('invert')" title="Invert Gravity (Fly Up)" class="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white text-xs transition-colors cursor-pointer">
              ⬆️ Invert
            </button>
          </div>

          <button onclick="restoreAntiGravity()" class="btn-glow-primary px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-lg bg-gradient-to-r from-purple-500 via-indigo-500 to-emerald-500 text-white cursor-pointer ml-1">
            <span>✨ Restore Navbar</span>
          </button>
        </div>
      `;

      document.body.appendChild(hud);
      this.hudElement = hud;
    }

    setGravityMode(mode) {
      if (!this.engine) return;

      if (mode === "zero") {
        this.engine.gravity.y = 0;
        this.engine.gravity.x = 0;
        // Give items a slight floating drift
        this.physicsItems.forEach(item => {
          Matter.Body.setVelocity(item.body, {
            x: (Math.random() - 0.5) * 1.5,
            y: (Math.random() - 0.5) * 1.5
          });
        });
        if (typeof showToast === "function") showToast("🌌 Zero-G Mode: Floating freely in orbital space!", "info");
      } else if (mode === "invert") {
        this.engine.gravity.y = -1.2;
        this.engine.gravity.x = 0;
        if (typeof showToast === "function") showToast("⬆️ Reverse Gravity: Inverted gravitational pull!", "info");
      } else {
        this.engine.gravity.y = 1.0;
        this.engine.gravity.x = 0;
        if (typeof showToast === "function") showToast("⬇️ Normal Gravity restored.", "info");
      }
    }

    restore() {
      if (!this.isActive || this.isRestoring) return;
      this.isRestoring = true;

      // Cancel physics render loop & stop engine
      if (this.animationFrameId) {
        cancelAnimationFrame(this.animationFrameId);
        this.animationFrameId = null;
      }

      if (this.runner) {
        Matter.Runner.stop(this.runner);
        this.runner = null;
      }

      if (this.hudElement) {
        this.hudElement.remove();
        this.hudElement = null;
      }

      if (this.onResizeHandler) {
        window.removeEventListener("resize", this.onResizeHandler);
      }

      // Smoothly animate all elements back to their initial navbar positions
      this.physicsItems.forEach(item => {
        const el = item.element;
        const init = item.initialRect;

        // Apply smooth spring transition
        el.style.transition = "transform 0.85s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.85s ease";
        el.style.transform = `translate3d(${init.left}px, ${init.top}px, 0px) rotate(0deg)`;
        el.style.boxShadow = "none";
        el.style.cursor = item.originalStyle.cursor || "";
      });

      // After transition completes, restore original layout flow
      setTimeout(() => {
        this.physicsItems.forEach(item => {
          const el = item.element;
          const orig = item.originalStyle;

          el.style.position = orig.position;
          el.style.top = orig.top;
          el.style.left = orig.left;
          el.style.width = orig.width;
          el.style.height = orig.height;
          el.style.margin = orig.margin;
          el.style.transform = orig.transform;
          el.style.zIndex = orig.zIndex;
          el.style.transition = orig.transition;
          el.style.boxShadow = orig.boxShadow;
          el.style.cursor = orig.cursor;
          el.style.userSelect = "";
          el.style.transformOrigin = "";
        });

        // Clear Matter.js world
        if (this.engine) {
          Matter.World.clear(this.engine.world, false);
          Matter.Engine.clear(this.engine);
          this.engine = null;
        }

        this.physicsItems = [];
        this.boundaries = [];
        this.isActive = false;
        this.isRestoring = false;

        if (typeof showToast === "function") {
          showToast("✨ Navbar restored to perfect grid alignment!", "success");
        }
      }, 850);
    }
  }

  // Initialize engine singleton
  window.antiGravity = new AntiGravityEngine();

})(window);
