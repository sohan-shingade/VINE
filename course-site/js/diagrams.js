/* ============================================================
   Visuals + animations: ambient background, the animated data
   pipeline SVG, the interactive NDVI widget, confetti.
   ============================================================ */
(function () {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- ambient floating "spores/grapes" background ---------- */
  function ambient() {
    const c = document.getElementById("bg-canvas");
    if (!c || reduced) return;
    const ctx = c.getContext("2d");
    let w, h, parts;
    function resize() {
      w = c.width = window.innerWidth;
      h = c.height = window.innerHeight;
      const n = Math.min(46, Math.floor(w / 28));
      parts = Array.from({ length: n }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        r: 1 + Math.random() * 3,
        vx: (Math.random() - 0.5) * 0.25,
        vy: -0.15 - Math.random() * 0.4,
        hue: Math.random() > 0.5 ? 140 : 286,
        a: 0.15 + Math.random() * 0.35,
      }));
    }
    resize();
    window.addEventListener("resize", resize);
    (function loop() {
      ctx.clearRect(0, 0, w, h);
      for (const p of parts) {
        p.x += p.vx; p.y += p.vy;
        if (p.y < -10) { p.y = h + 10; p.x = Math.random() * w; }
        if (p.x < -10) p.x = w + 10; if (p.x > w + 10) p.x = -10;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, 7);
        ctx.fillStyle = `hsla(${p.hue},55%,55%,${p.a})`;
        ctx.fill();
      }
      requestAnimationFrame(loop);
    })();
  }

  /* ---------- the animated D1 data-flow pipeline ---------- */
  // sources -> pipeline -> models -> eval -> serve, with flowing dots
  function pipelineSVG() {
    const sources = [
      { t: "🛰️ Sensors", s: "InfluxDB" },
      { t: "📷 Imagery", s: "STAC + S3" },
      { t: "🌤️ Weather", s: "Open-Meteo" },
    ];
    const models = [
      { t: "💧 D2 Irrigation", c: "#46a96a" },
      { t: "🌿 D3 Vision", c: "#8fd14f" },
      { t: "🍇 D4 Harvest", c: "#6b2d78" },
    ];
    const W = 900, H = 440;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="VINE data pipeline">`;
    s += `<defs>
      <linearGradient id="pipeGrad" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#2f7d4f"/><stop offset="1" stop-color="#6b2d78"/>
      </linearGradient>
      <filter id="soft"><feGaussianBlur stdDeviation="2.5"/></filter>
    </defs>`;

    // source nodes (left)
    sources.forEach((n, k) => {
      const y = 60 + k * 90;
      s += node(40, y, 150, n.t, n.s, "#fbf8f1", "#2f7d4f");
      s += path(`M190 ${y + 26} C 270 ${y + 26}, 300 220, 380 220`, "src" + k);
    });

    // D1 pipeline core (center)
    s += `<rect x="380" y="170" width="170" height="100" rx="18" fill="url(#pipeGrad)" filter="url(#soft)" opacity=".25"/>`;
    s += `<rect x="380" y="170" width="170" height="100" rx="18" fill="none" stroke="url(#pipeGrad)" stroke-width="2.5"/>`;
    s += text(465, 205, "D1 pipeline", 15, "700", "#2f7d4f");
    s += text(465, 228, "ingest · indices", 11, "500", "#6c6378");
    s += text(465, 246, "features · validate", 11, "500", "#6c6378");

    // model nodes (right)
    models.forEach((n, k) => {
      const y = 60 + k * 90;
      s += path(`M550 220 C 630 220, 660 ${y + 26}, 720 ${y + 26}`, "mdl" + k);
      s += node(720, y, 150, n.t, "", "#fbf8f1", n.c);
    });

    // flowing dots along each path
    const paths = ["src0", "src1", "src2", "mdl0", "mdl1", "mdl2"];
    paths.forEach((id, k) => {
      s += `<circle r="4.5" class="flow-dot">
        <animateMotion dur="${2.4 + (k % 3) * 0.4}s" repeatCount="indefinite" begin="${k * 0.35}s">
          <mpath href="#${id}"/>
        </animateMotion></circle>`;
    });

    s += `</svg>`;
    return s;

    function node(x, y, w, t, sub, fill, stroke) {
      let o = `<rect x="${x}" y="${y}" width="${w}" height="52" rx="14" fill="${fill}" stroke="${stroke}" stroke-width="2"/>`;
      o += text(x + w / 2, sub ? y + 24 : y + 31, t, 13, "600", "#1a1320");
      if (sub) o += text(x + w / 2, y + 40, sub, 10, "500", "#6c6378");
      return o;
    }
    function path(d, id) {
      return `<path id="${id}" d="${d}" fill="none" stroke="#e0d4c2" stroke-width="2" stroke-dasharray="4 5"/>`;
    }
    function text(x, y, t, size, weight, fill) {
      return `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="middle" font-family="Inter,sans-serif">${t}</text>`;
    }
  }

  /* ---------- interactive NDVI widget ---------- */
  function ndviWidget(slot) {
    slot.innerHTML = `
      <div class="ndvi-demo">
        <h4>🌿 Try it: compute NDVI</h4>
        <div class="sub">NDVI = (NIR − Red) / (NIR + Red). Drag the reflectance sliders — healthy plants reflect lots of near-infrared and absorb red.</div>
        <div class="ndvi-row">
          <label>NIR reflect.</label>
          <input type="range" min="0" max="1" step="0.01" value="0.55" id="ndvi-nir">
          <span class="val" id="ndvi-nir-v">0.55</span>
        </div>
        <div class="ndvi-row">
          <label>Red reflect.</label>
          <input type="range" min="0" max="1" step="0.01" value="0.12" id="ndvi-red">
          <span class="val" id="ndvi-red-v">0.12</span>
        </div>
        <div class="ndvi-out">
          <div class="ndvi-swatch" id="ndvi-swatch"></div>
          <div>
            <div class="ndvi-num"><b id="ndvi-val">0.64</b><span>NDVI (−1 … +1)</span></div>
            <div class="ndvi-verdict" id="ndvi-verdict"></div>
          </div>
        </div>
      </div>`;
    const nir = slot.querySelector("#ndvi-nir");
    const red = slot.querySelector("#ndvi-red");
    function color(v) {
      // -1 brown/soil -> 0 yellow -> 1 deep green
      if (v < 0) return "#8a6a44";
      if (v < 0.2) return "#c9a44a";
      if (v < 0.4) return "#b9c24a";
      if (v < 0.6) return "#7bbf46";
      return "#2f7d4f";
    }
    function verdict(v) {
      if (v < 0.1) return "Bare soil, water, or rock — no live canopy.";
      if (v < 0.3) return "Sparse or stressed vegetation.";
      if (v < 0.5) return "Moderate, growing canopy.";
      if (v < 0.7) return "Healthy, dense vegetation.";
      return "Very vigorous canopy.";
    }
    function update() {
      const n = +nir.value, r = +red.value;
      const denom = n + r;
      const v = denom === 0 ? 0 : (n - r) / denom;
      slot.querySelector("#ndvi-nir-v").textContent = n.toFixed(2);
      slot.querySelector("#ndvi-red-v").textContent = r.toFixed(2);
      slot.querySelector("#ndvi-val").textContent = v.toFixed(2);
      slot.querySelector("#ndvi-swatch").style.background = color(v);
      slot.querySelector("#ndvi-verdict").textContent = verdict(v);
    }
    nir.addEventListener("input", update);
    red.addEventListener("input", update);
    update();
  }

  /* ---------- confetti (grape colors) on course complete ---------- */
  function confetti() {
    if (reduced) return;
    const c = document.createElement("canvas");
    c.id = "confetti";
    document.body.appendChild(c);
    const ctx = c.getContext("2d");
    c.width = innerWidth; c.height = innerHeight;
    const colors = ["#6b2d78", "#2f7d4f", "#8fd14f", "#e6b34a", "#46a96a"];
    const bits = Array.from({ length: 160 }, () => ({
      x: Math.random() * c.width, y: -20 - Math.random() * c.height,
      r: 4 + Math.random() * 6, c: colors[(Math.random() * colors.length) | 0],
      vy: 2 + Math.random() * 4, vx: (Math.random() - 0.5) * 3,
      rot: Math.random() * 6, vr: (Math.random() - 0.5) * 0.3,
    }));
    let t = 0;
    (function loop() {
      ctx.clearRect(0, 0, c.width, c.height);
      bits.forEach((b) => {
        b.y += b.vy; b.x += b.vx; b.rot += b.vr;
        ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.rot);
        ctx.fillStyle = b.c; ctx.fillRect(-b.r / 2, -b.r / 2, b.r, b.r);
        ctx.restore();
      });
      t++;
      if (t < 200) requestAnimationFrame(loop);
      else c.remove();
    })();
  }

  window.VIZ = { ambient, pipelineSVG, ndviWidget, confetti };
})();
