/* ============================================================
   App: hash router, landing page, module renderer, progress
   (localStorage), scroll-reveal, theme toggle, mobile nav.
   ============================================================ */
(function () {
  const PROG_KEY = "vine-course-progress";
  const THEME_KEY = "vine-course-theme";

  // flatten modules in order
  const MODS = [];
  COURSE.parts.forEach((p) => p.modules.forEach((m) => MODS.push({ ...m, partTitle: p.title })));
  const bySlug = Object.fromEntries(MODS.map((m) => [m.slug, m]));

  /* ---------- progress ---------- */
  function getProgress() {
    try { return new Set(JSON.parse(localStorage.getItem(PROG_KEY) || "[]")); }
    catch { return new Set(); }
  }
  function setProgress(set) {
    localStorage.setItem(PROG_KEY, JSON.stringify([...set]));
    updateProgressUI();
  }
  function updateProgressUI() {
    const done = getProgress();
    const pct = Math.round((done.size / MODS.length) * 100);
    const ring = document.getElementById("ring-fg");
    const circ = 2 * Math.PI * 52;
    ring.style.strokeDashoffset = circ * (1 - pct / 100);
    document.getElementById("progress-pct").textContent = pct + "%";
    document.querySelectorAll(".nav-link").forEach((a) => {
      const slug = a.dataset.slug;
      a.classList.toggle("done", done.has(slug));
    });
  }

  /* ---------- sidebar nav ---------- */
  function buildNav() {
    const nav = document.getElementById("nav");
    let html = "";
    COURSE.parts.forEach((p) => {
      html += `<div class="nav-part">${p.title}</div>`;
      p.modules.forEach((m) => {
        html += `<a class="nav-link" data-slug="${m.slug}" href="#/${m.slug}">
          <span class="nav-num">${m.num}</span>
          <span class="nav-txt">${m.title}</span>
          <span class="nav-check">✓</span>
        </a>`;
      });
    });
    nav.innerHTML = html;
  }

  function setActiveNav(slug) {
    document.querySelectorAll(".nav-link").forEach((a) =>
      a.classList.toggle("active", a.dataset.slug === slug));
  }

  /* ---------- landing page ---------- */
  function renderHome() {
    const icons = ["🌱", "☸️", "🤖", "🍇", "🚀"];
    let parts = "";
    COURSE.parts.forEach((p, k) => {
      const links = p.modules.map((m) =>
        `<li><a href="#/${m.slug}">${m.title}</a></li>`).join("");
      parts += `<div class="part-card reveal">
        <span class="pc-icon">${icons[k] || "📘"}</span>
        <h3>${p.title}</h3>
        <p>${p.blurb}</p>
        <ol>${links}</ol>
      </div>`;
    });

    const c = document.getElementById("content");
    c.innerHTML = `
      <div class="module">
        <section class="hero">
          <div class="eyebrow">GSoC 2026 · Iron Horse Vineyards · NRP</div>
          <h1>Build <span class="grad">VINE</span><br/>from zero.</h1>
          <p class="lede">An interactive course that teaches every prerequisite — ETL, time-series, geospatial, Kubernetes, the NRP platform, and ML/MLOps — then has you build all six deliverables yourself.</p>
          <div class="hero-cta">
            <a class="btn btn-primary" href="#/${MODS[0].slug}">Start module 1 →</a>
            <a class="btn btn-ghost" href="#resume" id="resume-btn">Resume where I left off</a>
          </div>
          <div class="stats">
            <div class="stat"><b>${MODS.length}</b><span>modules</span></div>
            <div class="stat"><b>5</b><span>parts</span></div>
            <div class="stat"><b>6</b><span>deliverables</span></div>
            <div class="stat"><b>0→1</b><span>prereqs assumed</span></div>
          </div>
        </section>

        <div class="diagram-wrap reveal">
          ${VIZ.pipelineSVG()}
          <div class="diagram-caption">What you'll build: three raw data sources → one shared pipeline → three model tracks → evaluation → a deployed API. Each module teaches one piece.</div>
        </div>

        <h2 class="reveal" style="text-align:center">The path</h2>
        <div class="parts-grid">${parts}</div>

        <div class="card-block reveal">
          <div class="cb-title">▶ before you start</div>
          <p>Clone the repo and run <code>make setup</code> (creates the venv, installs everything, wires pre-commit). Module 1 assumes that worked. Everything you do here runs against the <strong>real</strong> VINE codebase, data, and the NRP cluster — this is not a toy.</p>
        </div>
      </div>`;

    document.getElementById("resume-btn").addEventListener("click", (e) => {
      e.preventDefault();
      const done = getProgress();
      const next = MODS.find((m) => !done.has(m.slug)) || MODS[0];
      location.hash = "#/" + next.slug;
    });

    setActiveNav(null);
    observeReveal();
    scrollTop();
  }

  /* ---------- module page ---------- */
  function renderModule(slug) {
    const m = bySlug[slug];
    if (!m) { renderHome(); return; }
    const idx = MODS.findIndex((x) => x.slug === slug);
    const prev = MODS[idx - 1], next = MODS[idx + 1];
    const done = getProgress().has(slug);

    const body = MD.render(m.body);

    const c = document.getElementById("content");
    c.innerHTML = `
      <article class="module">
        <div class="module-head reveal">
          <div class="module-kicker">${m.partTitle} · Module ${m.num} of ${MODS.length}</div>
          <h1>${m.title}</h1>
          <p class="hook">${m.hook}</p>
        </div>
        <div class="module-body">${body}</div>
        <div class="module-footer">
          <button class="complete-btn ${done ? "done" : ""}" id="complete">
            ${done ? "✓ Completed" : "Mark module complete"}
          </button>
          <div class="pager">
            ${prev
              ? `<a href="#/${prev.slug}"><small>← Previous</small><b>${prev.title}</b></a>`
              : `<a class="disabled"><small>← Previous</small><b>—</b></a>`}
            ${next
              ? `<a class="next" href="#/${next.slug}"><small>Next →</small><b>${next.title}</b></a>`
              : `<a class="next" href="#/"><small>Next →</small><b>🎉 Finish</b></a>`}
          </div>
        </div>
      </article>`;

    // mount widgets
    c.querySelectorAll(".widget-slot").forEach((slot) => {
      if (slot.dataset.widget === "ndvi") VIZ.ndviWidget(slot);
      if (slot.dataset.widget === "pipeline") slot.innerHTML = `<div class="diagram-wrap">${VIZ.pipelineSVG()}</div>`;
    });

    // wrap hands-on section (h2 containing "Hands-on") for numbered styling
    tagHandsOn(c);
    decorateBlocks(c);

    // complete button
    document.getElementById("complete").addEventListener("click", () => {
      const p = getProgress();
      if (p.has(slug)) { p.delete(slug); }
      else {
        p.add(slug);
        if (p.size === MODS.length) VIZ.confetti();
      }
      setProgress(p);
      renderModule(slug); // re-render button state
    });

    setActiveNav(slug);
    observeReveal();
    scrollTop();
    closeMobileNav();
  }

  // turn the ordered list right after a "Hands-on" heading into stepper style
  function tagHandsOn(root) {
    root.querySelectorAll("h2").forEach((h) => {
      if (/hands-on/i.test(h.textContent)) {
        let el = h.nextElementSibling;
        while (el && el.tagName !== "H2") {
          if (el.tagName === "OL") el.parentElement && el.closest(".hands-on") ? null : wrap(el);
          el = el.nextElementSibling;
        }
      }
    });
    function wrap(ol) {
      const d = document.createElement("div");
      d.className = "hands-on";
      ol.parentNode.insertBefore(d, ol);
      d.appendChild(ol);
    }
  }

  // wrap Objectives / Self-test sections into cards
  function decorateBlocks(root) {
    // nothing extra for now; callouts handled by markdown
  }

  /* ---------- scroll reveal ---------- */
  let io;
  function observeReveal() {
    if (io) io.disconnect();
    io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.08 });
    document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
    // auto-reveal module body children progressively
    const body = document.querySelector(".module-body");
    if (body) {
      [...body.children].forEach((el, i) => {
        el.classList.add("reveal");
        io.observe(el);
      });
    }
  }

  /* ---------- reading progress bar ---------- */
  function readingBar() {
    const bar = document.getElementById("read-progress");
    const main = document.getElementById("content");
    window.addEventListener("scroll", () => {
      const h = main.scrollHeight - window.innerHeight;
      const p = h > 0 ? Math.min(100, (window.scrollY / h) * 100) : 0;
      bar.style.width = p + "%";
    }, { passive: true });
  }

  function scrollTop() { window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" }); }

  /* ---------- theme ---------- */
  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const dark = saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (dark) document.documentElement.setAttribute("data-theme", "dark");
    document.getElementById("theme-toggle").addEventListener("click", () => {
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      if (isDark) { document.documentElement.removeAttribute("data-theme"); localStorage.setItem(THEME_KEY, "light"); }
      else { document.documentElement.setAttribute("data-theme", "dark"); localStorage.setItem(THEME_KEY, "dark"); }
    });
  }

  /* ---------- mobile nav ---------- */
  function initMobileNav() {
    const sb = document.getElementById("sidebar");
    document.getElementById("menu-toggle").addEventListener("click", () => sb.classList.toggle("open"));
  }
  function closeMobileNav() { document.getElementById("sidebar").classList.remove("open"); }

  /* ---------- router ---------- */
  function route() {
    const hash = location.hash.replace(/^#\/?/, "");
    if (!hash || hash === "" || hash === "/") renderHome();
    else renderModule(hash);
    updateProgressUI();
  }

  /* ---------- init ---------- */
  function init() {
    buildNav();
    initTheme();
    initMobileNav();
    readingBar();
    VIZ.ambient();
    document.getElementById("reset-progress").addEventListener("click", () => {
      if (confirm("Reset all course progress?")) setProgress(new Set());
    });
    window.addEventListener("hashchange", route);
    route();
    updateProgressUI();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
