document.addEventListener("DOMContentLoaded", () => {
  const API = "https://codedebt-guardian-api.onrender.com";

  // ═══ PARTICLE CANVAS ═══
  (function initParticles() {
    const canvas = document.getElementById("particle-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let W, H, particles = [];
    const N = 60;

    function resize() {
      W = canvas.width  = window.innerWidth;
      H = canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    for (let i = 0; i < N; i++) {
      particles.push({
        x: Math.random() * 9999,
        y: Math.random() * 9999,
        vx: (Math.random() - 0.5) * 0.25,
        vy: (Math.random() - 0.5) * 0.25,
        r: Math.random() * 1.4 + 0.4,
        a: Math.random() * 0.5 + 0.1,
      });
    }

    const COLORS = ["#9d7aff", "#00d4ff", "#00e5a0"];
    function draw() {
      ctx.clearRect(0, 0, W, H);
      for (let p of particles) {
        p.x = ((p.x + p.vx + W) % W);
        p.y = ((p.y + p.vy + H) % H);
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = COLORS[Math.floor(Math.random() * COLORS.length)];
        ctx.globalAlpha = p.a;
        ctx.fill();
        ctx.globalAlpha = 1;
      }
      // Connecting lines
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx*dx + dy*dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = "#9d7aff";
            ctx.globalAlpha = (1 - dist/120) * 0.12;
            ctx.lineWidth = 0.5;
            ctx.stroke();
            ctx.globalAlpha = 1;
          }
        }
      }
      requestAnimationFrame(draw);
    }
    draw();
  })();

  // ═══ COUNTER ANIMATION ═══
  document.querySelectorAll("[data-count]").forEach(el => {
    const target = parseInt(el.dataset.count);
    let current = 0;
    const step = target / 40;
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = Math.floor(current) + (el.dataset.suffix || "");
      if (current >= target) clearInterval(timer);
    }, 30);
  });

  // ═══ NAV SCROLL ═══
  const nav = document.getElementById("nav");
  window.addEventListener("scroll", () => {
    nav?.classList.toggle("scrolled", window.scrollY > 40);
  });

  // ═══ HAMBURGER ═══
  const hamburger = document.getElementById("nav-hamburger");
  const navLinks  = document.getElementById("nav-links");
  hamburger?.addEventListener("click", () => {
    hamburger.classList.toggle("open");
    navLinks.classList.toggle("open");
  });
  navLinks?.querySelectorAll("a").forEach(a => {
    a.addEventListener("click", () => {
      hamburger.classList.remove("open");
      navLinks.classList.remove("open");
    });
  });

  // ═══ NAV CTA SMOOTH SCROLL ═══
  document.getElementById("nav-cta")?.addEventListener("click", e => {
    e.preventDefault();
    document.getElementById("hero-scan")?.scrollIntoView({ behavior: "smooth" });
  });

  // ═══ TOAST ═══
  function toast(msg, type = "info") {
    const root = document.getElementById("toast-root");
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    root.appendChild(el);
    setTimeout(() => el.remove(), 4500);
  }

  // ═══ COST TABLE ═══
  const COSTS = {
    hardcoded_password: 106.25, hardcoded_api_key: 106.25, hardcoded_token: 106.25,
    long_method: 297.50, bare_except: 63.75, god_class: 212.50,
    missing_docstring: 29.75, unpinned_dependencies: 85.00, too_many_parameters: 63.75,
    syntax_error: 42.50,
  };
  const DEFAULT_COST = 42.50;

  // ═══ STATE ═══
  let currentRepoUrl = "";
  let analysisData = null;

  // Wake backend silently
  fetch(`${API}/health`).catch(() => {});

  // ═══ DEMO FILL ═══
  document.getElementById("demo-fill")?.addEventListener("click", () => {
    document.getElementById("repo-url").value = "https://github.com/Priyanshjain10/codedebt-guardian";
  });

  // ═══ TAB SYSTEM ═══
  document.getElementById("tab-bar")?.addEventListener("click", e => {
    const btn = e.target.closest(".tab-btn");
    if (!btn) return;
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.style.display = "none");
    btn.classList.add("active");
    const panel = document.getElementById(`panel-${btn.dataset.tab}`);
    if (panel) panel.style.display = "block";
  });

  // ═══ SCAN ═══
  const scanBtn  = document.getElementById("scan-btn");
  const repoInput = document.getElementById("repo-url");

  repoInput?.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); scanBtn?.click(); }
  });
  scanBtn?.addEventListener("click", startScan);
  document.getElementById("retry-btn")?.addEventListener("click", startScan);

  async function startScan() {
    let url = repoInput.value.trim();
    if (!url) return;
    if (!url.startsWith("http")) url = "https://" + url;
    currentRepoUrl = url;

    const label = document.getElementById("scan-btn-label");
    const icon  = document.getElementById("scan-btn-icon");

    scanBtn.disabled = true;
    label.textContent = "Scanning…";
    icon.className = "fa-solid fa-circle-notch fa-spin";

    const sec = document.getElementById("results-section");
    sec.classList.remove("hidden");
    sec.scrollIntoView({ behavior: "smooth", block: "start" });

    show("progress-wrap");
    hide("skeleton-wrap");
    hide("error-state");
    hide("results-dashboard");

    const log = document.getElementById("progress-log");
    log.innerHTML = "";
    logLine(log, `▶ Connecting to ${url}…`);

    const wakeTimer = setTimeout(() => {
      document.getElementById("wake-banner")?.classList.remove("hidden");
      logLine(log, "⏳ Waking analysis engine (~30s cold start)…", "warn");
    }, 3000);

    try {
      const resp = await fetch(`${API}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: url }),
      });

      clearTimeout(wakeTimer);
      document.getElementById("wake-banner")?.classList.add("hidden");

      if (!resp.ok) throw new Error(`API error ${resp.status}`);

      const reader  = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "", finalData = null, streamErr = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          const t = line.trim();
          if (!t) continue;
          try {
            const ev = JSON.parse(t);
            if (ev.status === "progress") {
              logLine(log, ev.message);
            } else if (ev.status === "quota_exceeded") {
              toast("AI quota reached — static results only. Resets ~24h.", "warn");
            } else if (ev.status === "complete") {
              finalData = ev.data;
              window.lastAnalysisData = ev.data;
              window.lastScanId = ev.scan_id || null;
              if (ev.scan_id) pushScanUrl(ev.scan_id);
              logLine(log, "✓ Analysis complete.", "ok");
            } else if (ev.status === "error") {
              streamErr = true;
              logLine(log, ev.message, "err");
            }
          } catch (_) {}
        }
      }

      if (buffer.trim()) {
        try {
          const ev = JSON.parse(buffer.trim());
          if (ev.status === "complete") {
            finalData = ev.data;
            window.lastAnalysisData = ev.data;
            window.lastScanId = ev.scan_id || null;
            if (ev.scan_id) pushScanUrl(ev.scan_id);
          }
          if (ev.status === "error") { streamErr = true; logLine(log, ev.message, "err"); }
        } catch (_) {}
      }

      if (streamErr || !finalData) throw new Error("Stream ended without result");

      analysisData = finalData;
      hide("progress-wrap");
      show("skeleton-wrap");
      setTimeout(() => {
        hide("skeleton-wrap");
        renderDashboard(finalData);
        show("results-dashboard");
      }, 500);

    } catch (err) {
      clearTimeout(wakeTimer);
      document.getElementById("wake-banner")?.classList.add("hidden");
      hide("progress-wrap");
      show("error-state");
    } finally {
      scanBtn.disabled = false;
      label.textContent = "Scan Repository";
      icon.className = "fa-solid fa-arrow-right";
    }
  }

  function pushScanUrl(scanId) {
    const u = new URL(window.location);
    u.searchParams.set("scan", scanId);
    window.history.pushState({}, "", u);
    document.getElementById("btn-share")?.classList.remove("hidden");
  }

  // ═══ RENDER DASHBOARD ═══
  function renderDashboard(raw) {
    const issues   = (raw.ranked_issues || []).slice(0, 25);
    const fixes    = raw.fix_proposals || [];
    const tdr      = raw.tdr || {};
    const hotspots = raw.hotspots || [];
    const summary  = raw.summary || {};
    summary.files_scanned = summary.files_scanned || raw.detection?.files_scanned || raw.files_scanned || "—";

    renderGrade(tdr);
    renderStats(summary, tdr);
    renderCost(tdr);
    renderLedger(issues);
    renderHotspots(hotspots);
    renderFixes(fixes);

    const fc = document.getElementById("fixes-count");
    if (fc) fc.textContent = fixes.length || "";

    // Cascade entrance
    document.querySelectorAll("#results-dashboard .dash-card").forEach((el, i) => {
      el.style.opacity = "0";
      el.style.transform = "translateY(18px)";
      setTimeout(() => {
        el.style.transition = "opacity 0.5s ease, transform 0.5s ease";
        el.style.opacity = "1";
        el.style.transform = "translateY(0)";
      }, i * 90 + 60);
    });
  }

  // Grade
  function renderGrade(tdr) {
    const el = document.getElementById("grade-wrap");
    if (!el) return;
    if (!tdr?.grade) {
      el.innerHTML = `<div class="grade-ring grade-C"><span>?</span></div><div class="grade-score">Unavailable</div>`;
      return;
    }
    const pct = Math.round(tdr.health_score || 0);
    const deg = Math.round((pct / 100) * 360);
    el.innerHTML = `
      <div class="grade-ring grade-${tdr.grade}" style="--grade-pct:${deg}deg">
        <span>${tdr.grade}</span>
      </div>
      <div class="grade-score">${pct}/100 health score</div>
      ${tdr.interpretation ? `<div class="grade-interpret">${safeText(tdr.interpretation)}</div>` : ""}
    `;
  }

  // Stats
  function renderStats(summary, tdr) {
    const el = document.getElementById("summary-stats");
    if (!el) return;
    const rows = [
      ["Files Scanned",  summary.files_scanned || "—", ""],
      ["Issues Found",   summary.total_issues || 0,    ""],
      ["Critical",       summary.critical || 0,        "color:var(--red)"],
      ["High",           summary.high || 0,             "color:var(--orange)"],
      ["Fixes Proposed", summary.fixes_proposed || 0,  "color:var(--green)"],
    ];
    el.innerHTML = rows.map(([k,v,s]) => `
      <div class="stat-row">
        <span class="stat-key">${k}</span>
        <span class="stat-val" style="${s}">${v}</span>
      </div>
    `).join("");
  }

  // Cost
  function renderCost(tdr) {
    const el = document.getElementById("debt-total-wrap");
    if (!el) return;
    const cost = tdr?.remediation_cost_usd || 0;
    el.innerHTML = `
      <div class="cost-num">$${Math.round(cost).toLocaleString("en-US")}</div>
      <div class="cost-label">Estimated remediation cost</div>
    `;
    // Animate the number
    animateCounter(el.querySelector(".cost-num"), 0, Math.round(cost), "$");
  }

  function animateCounter(el, from, to, prefix = "") {
    if (!el || to === 0) return;
    let current = from;
    const step = to / 50;
    const timer = setInterval(() => {
      current = Math.min(current + step, to);
      el.textContent = `${prefix}${Math.floor(current).toLocaleString("en-US")}`;
      if (current >= to) clearInterval(timer);
    }, 20);
  }

  // Ledger
  function renderLedger(issues) {
    const el = document.getElementById("panel-ledger");
    if (!el) return;
    if (!issues?.length) {
      el.innerHTML = `<div class="empty-state"><i class="fa-solid fa-circle-check" style="color:var(--green);font-size:24px;margin-bottom:8px;display:block;"></i>Clean codebase — no issues detected.</div>`;
      return;
    }
    const rows = issues.map(iss => ({
      ...iss,
      cost: COSTS[iss.type] || iss.cost || DEFAULT_COST,
      sev:  (iss.severity || iss.priority || "LOW").toUpperCase(),
    })).sort((a,b) => b.cost - a.cost);

    const total = rows.reduce((s, r) => s + r.cost, 0);
    el.innerHTML = `
      <table class="ledger-table">
        <thead><tr>
          <th>Issue</th><th>File</th><th>Severity</th><th style="text-align:right">Cost</th>
        </tr></thead>
        <tbody>${rows.map(r => `
          <tr>
            <td class="issue-cell">${safeText((r.type||"unknown").replace(/_/g," "))}</td>
            <td class="file-cell">${safeText(r.location||r.file||"—")}</td>
            <td><span class="sev-pill sev-${r.sev}">${r.sev}</span></td>
            <td class="cost-cell">$${r.cost.toFixed(0)}</td>
          </tr>
        `).join("")}</tbody>
        <tfoot><tr>
          <td colspan="3" style="padding:10px;font-size:12px;color:var(--text-2);">Total</td>
          <td class="cost-cell">$${Math.round(total).toLocaleString("en-US")}</td>
        </tr></tfoot>
      </table>
    `;
  }

  // Hotspots
  function renderHotspots(hotspots) {
    const el = document.getElementById("panel-hotspots");
    if (!el) return;
    if (!hotspots?.length) {
      el.innerHTML = `<div class="empty-state">No hotspot data for this scan.</div>`;
      return;
    }
    const max = Math.max(...hotspots.map(h => h.hotspot_score||h.debt_score||h.score||0), 1);
    el.innerHTML = `<div class="hotspot-list">${hotspots.map(h => {
      const score = h.hotspot_score||h.debt_score||h.score||0;
      const pct = (score/max)*100;
      return `
        <div class="hs-item">
          <div class="hs-name" title="${safeText(h.filepath||h.file||h.filename||'')}">${safeText(h.filepath||h.file||h.filename||'unknown')}</div>
          <div class="hs-track"><div class="hs-bar" style="width:${pct}%"></div></div>
          <div class="hs-score">${score.toFixed(1)}</div>
        </div>
      `;
    }).join("")}</div>`;
  }

  // Fix Proposals
  function renderFixes(fixes) {
    const el = document.getElementById("panel-fixes");
    if (!el) return;
    if (!fixes?.length) {
      el.innerHTML = `<div class="empty-state">No fix proposals for this scan.</div>`;
      return;
    }

    const UNFIXABLE = new Set(["long_method","god_class","too_many_parameters","missing_docstring","satd_defect","satd_design"]);

    el.innerHTML = `<div class="fixes-list">${fixes.map((f, i) => {
      const isManual = UNFIXABLE.has(f.issue_type);
      const hasCode  = f.before_code && f.after_code;
      return `
        <div class="fix-card" id="fix-card-${i}">
          <div class="fix-header" data-fix="${i}">
            <div class="fix-left">
              <div class="fix-type">${safeText((f.issue_type||"fix").replace(/_/g," "))}</div>
              <div class="fix-file">${safeText(f.file||"")}${f.line ? ":"+f.line : ""}</div>
            </div>
            <div class="fix-right">
              <span class="fix-time"><i class="fa-regular fa-clock"></i> ${safeText(f.estimated_time||f.effort_to_fix||"N/A")}</span>
              <button class="btn-pr ${isManual ? "manual" : ""}" ${isManual ? "disabled title='Requires manual refactoring'" : ""}>
                ${isManual ? "Manual Fix" : "Create PR"}
              </button>
              <i class="fa-solid fa-chevron-down fix-chevron"></i>
            </div>
          </div>
          <div class="fix-body">
            <div class="fix-body-inner">
              <p class="fix-summary">${safeText(f.fix_summary||f.description||"")}</p>
              ${hasCode ? `
                <div class="diff-wrap">
                  <div class="diff-pane diff-before">
                    <div class="diff-pane-label">Before</div>
                    <pre><code class="language-python">${escHtml(f.before_code)}</code></pre>
                  </div>
                  <div class="diff-pane diff-after">
                    <div class="diff-pane-label">After</div>
                    <pre><code class="language-python">${escHtml(f.after_code)}</code></pre>
                  </div>
                </div>
              ` : ""}
            </div>
          </div>
        </div>
      `;
    }).join("")}</div>`;

    // Syntax highlight
    el.querySelectorAll("pre code").forEach(b => { try { hljs.highlightElement(b); } catch(_){} });

    // Expand toggle
    el.querySelectorAll(".fix-header").forEach(h => {
      h.addEventListener("click", () => {
        document.getElementById(`fix-card-${h.dataset.fix}`)?.classList.toggle("expanded");
      });
    });

    // PR buttons
    el.querySelectorAll(".btn-pr:not([disabled])").forEach((btn, i) => {
      btn.addEventListener("click", async e => {
        e.stopPropagation();
        if (btn.dataset.busy) return;
        btn.dataset.busy = "1";
        btn.disabled = true;
        btn.textContent = "Creating…";

        const scanId = window.lastScanId;
        if (!scanId) {
          btn.disabled = false; btn.textContent = "Create PR"; delete btn.dataset.busy;
          toast("Run a scan first.", "error"); return;
        }

        const ctrl = new AbortController();
        const timeout = setTimeout(() => ctrl.abort(), 60000);

        try {
          const resp = await fetch(`${API}/fix`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: ctrl.signal,
            body: JSON.stringify({ repo_url: currentRepoUrl, scan_id: scanId, fix_index: i }),
          });
          clearTimeout(timeout);

          if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `Server ${resp.status}`);
          }

          const pr = await resp.json();
          if (pr.status === "skipped") {
            btn.textContent = "Manual Fix";
            btn.className = "btn-pr manual";
            btn.disabled = true;
            toast("This issue requires manual refactoring.", "info");
            return;
          }
          btn.textContent = "PR Created ✓";
          btn.className = "btn-pr created";
          btn.onclick = () => window.open(pr.pr_url, "_blank");
          document.getElementById(`fix-card-${i}`)?.classList.add("pr-created");
          toast("Pull Request created successfully!", "success");

        } catch(err) {
          clearTimeout(timeout);
          delete btn.dataset.busy;
          btn.disabled = false;
          btn.textContent = "Create PR";
          toast(err.name === "AbortError" ? "Timed out — try again." : `Failed: ${err.message}`, "error");
        }
      });
    });
  }

  // ═══ CTO REPORT ═══
  document.getElementById("btn-report")?.addEventListener("click", async () => {
    if (!currentRepoUrl) return;
    const btn = document.getElementById("btn-report");
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Generating…';
    try {
      const body = { repo_url: currentRepoUrl };
      if (window.lastScanId) body.scan_id = window.lastScanId;
      if (window.lastAnalysisData) body.analysis_data = window.lastAnalysisData;
      const resp = await fetch(`${API}/report`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body) });
      if (!resp.ok) throw new Error(`${resp.status}`);
      const data = await resp.json();
      const blob = new Blob([data.html], { type:"text/html" });
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "cto_debt_report.html" });
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      toast("Report downloaded!", "success");
    } catch(err) {
      toast("Report failed: " + err.message, "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-file-pdf"></i> Download CTO Report';
    }
  });

  // ═══ AUTO-FIX ═══
  document.getElementById("btn-autofix")?.addEventListener("click", async () => {
    if (!currentRepoUrl) return;
    const btn = document.getElementById("btn-autofix");
    const res = document.getElementById("autofix-results");
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Creating PRs…';
    res.innerHTML = ""; res.classList.remove("hidden");

    try {
      const resp = await fetch(`${API}/analyze`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ repo_url: currentRepoUrl, auto_fix: true, max_prs: 3 }),
      });
      if (!resp.ok) throw new Error(`${resp.status}`);
      const reader = resp.body.getReader();
      const dec    = new TextDecoder();
      let buf = "", prs = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n"); buf = lines.pop();
        for (const line of lines) {
          const t = line.trim(); if (!t) continue;
          try {
            const ev = JSON.parse(t);
            if (ev.status === "progress") res.innerHTML += `<div class="prog-line">${safeText(ev.message)}</div>`;
            if (ev.status === "complete" && ev.data?.pull_requests) prs = ev.data.pull_requests;
            if (ev.status === "prs_created" && ev.prs) prs = ev.prs;
          } catch(_) {}
        }
      }
      if (prs.length) {
        res.innerHTML = prs.map(pr => `
          <a href="${safeText(pr.html_url||pr.url||"#")}" target="_blank" class="pr-link">
            <i class="fa-solid fa-code-pull-request"></i>
            PR #${pr.number}: ${safeText((pr.title||"Fix").slice(0,70))}
          </a>
        `).join("");
        btn.innerHTML = `<i class="fa-solid fa-check"></i> ${prs.length} PR${prs.length>1?"s":""} Created`;
        btn.style.background = "var(--green)"; btn.style.color = "#000";
        toast(`${prs.length} pull request(s) created!`, "success");
      } else {
        res.innerHTML = '<div class="prog-line warn">No PRs created — ensure GITHUB_TOKEN has write access.</div>';
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Retry';
      }
    } catch(err) {
      res.innerHTML = `<div class="prog-line err">Error: ${safeText(err.message)}</div>`;
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Auto-Fix Top 3';
    }
  });

  // ═══ SHARE ═══
  document.getElementById("btn-share")?.addEventListener("click", () => {
    navigator.clipboard.writeText(window.location.href)
      .then(() => toast("Scan link copied!", "success"))
      .catch(() => toast("Could not copy.", "error"));
  });

  // ═══ AUTO-LOAD FROM URL ═══
  const sharedId = new URLSearchParams(window.location.search).get("scan");
  if (sharedId) {
    (async () => {
      try {
        const resp = await fetch(`${API}/scan/${sharedId}`);
        if (!resp.ok) throw new Error("Not found");
        const result = await resp.json();
        window.lastScanId = sharedId;
        window.lastAnalysisData = result.data;
        renderDashboard(result.data);
        show("results-section");
        show("results-dashboard");
        document.getElementById("results-section")?.scrollIntoView({ behavior:"smooth" });
        document.getElementById("btn-share")?.classList.remove("hidden");
      } catch {
        toast("Could not load shared scan — it may have expired.", "error");
      }
    })();
  }

  // ═══ UTILS ═══
  function show(id) { document.getElementById(id)?.classList.remove("hidden"); }
  function hide(id) { document.getElementById(id)?.classList.add("hidden"); }

  function safeText(str) {
    const d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
  }

  function escHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  function logLine(container, msg, type = "") {
    const d = document.createElement("div");
    d.className = `prog-line ${type}`;
    d.textContent = msg;
    container.appendChild(d);
    container.scrollTop = container.scrollHeight;
  }

});
