let DATA = null;

async function init() {
  const r = await fetch('data.json');
  DATA = await r.json();
  buildNav();
  handleRoute();
  window.addEventListener('hashchange', handleRoute);
}

function buildNav() {
  const nav = document.getElementById('nav');
  let html = '<div class="title">Ramco PO · Journey Model</div>';
  html += '<div class="nav-item" data-go="#home">▸ Home</div>';

  const user = [], admin = [];
  for (const [name, a] of Object.entries(DATA.activities)) {
    if (a.is_user_facing) user.push([name, a]); else admin.push([name, a]);
  }

  html += '<div class="section">USER-FACING JOURNEYS (' + user.length + ')</div>';
  for (const [name, a] of user) {
    html += `<div class="nav-item" data-go="#act/${name}"><span>${name}</span><span class="count">${a.splice_summary?.total ?? 0}</span></div>`;
  }
  html += '<div class="section">ADMIN / SUB-AREA</div>';
  for (const [name, a] of admin) {
    html += `<div class="nav-item" data-go="#act/${name}"><span>${name}</span><span class="count">${a.splice_summary?.total ?? 0}</span></div>`;
  }
  nav.innerHTML = html;
  nav.querySelectorAll('.nav-item').forEach(el =>
    el.addEventListener('click', () => location.hash = el.dataset.go));
}

function handleRoute() {
  const hash = location.hash || '#home';
  document.querySelectorAll('.nav-item').forEach(el =>
    el.classList.toggle('active', el.dataset.go === hash));
  if (hash === '#home') return renderHome();
  if (hash.startsWith('#act/')) return renderActivity(hash.slice(5));
  renderHome();
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function renderHome() {
  const user = Object.entries(DATA.activities).filter(([_,a]) => a.is_user_facing);
  let html = '<h1 class="page-title">Ramco Purchase Order · journey model</h1>';
  html += '<div class="page-sub">Deterministic model built from screen artifacts, service catalog, and SP code. Click any activity to inspect.</div>';
  html += '<div class="summary-grid">';
  html += `<div class="stat"><div class="lbl">User-facing journeys</div><div class="big">${user.length}</div></div>`;
  const totalSplices = user.reduce((s, [_,a]) => s + (a.splice_summary?.total ?? 0), 0);
  html += `<div class="stat"><div class="lbl">Total splices</div><div class="big">${totalSplices}</div></div>`;
  const totalSlots = user.reduce((s, [_,a]) => s + a.screens.reduce((ss, sc) => ss + sc.slot_count, 0), 0);
  html += `<div class="stat"><div class="lbl">Total slots</div><div class="big">${totalSlots}</div></div>`;
  html += `<div class="stat"><div class="lbl">Cross-journey edges</div><div class="big">${DATA.graph?.edge_count ?? 0}</div></div>`;
  html += '</div>';

  html += '<h2 class="section-h">Activities</h2>';
  for (const [name, a] of user) {
    const spine = a.canonical_spine?.filter(s => s.phase === 'commit').length || 0;
    html += `<div class="card" style="cursor:pointer;" onclick="location.hash='#act/${name}'">`;
    html += `<div style="display:flex; gap:16px; align-items:baseline;">`;
    html += `<span class="mono" style="color:var(--purple);">${name}</span>`;
    html += `<span style="flex:1; font-weight:500;">${esc(a.description)}</span>`;
    html += `<span class="mono" style="color:var(--muted);">${spine} commit · ${a.splice_summary?.total ?? 0} splices · ${a.screens.length} screens</span>`;
    html += `</div></div>`;
  }
  document.getElementById('content').innerHTML = html;
}

function renderActivity(name) {
  const a = DATA.activities[name];
  if (!a) { document.getElementById('content').innerHTML = `<h1>Not found: ${esc(name)}</h1>`; return; }

  let html = `<h1 class="page-title">${esc(name)} <span style="font-size:24px; color:var(--muted); font-weight:400;">${esc(a.description)}</span></h1>`;
  html += `<div class="page-sub">main screen: ${esc(a.main_screen)} · ${a.screen_count} screens · ${a.canonical_spine?.length ?? 0} canonical-spine steps · ${a.splice_summary?.total ?? 0} splices</div>`;

  // Canonical spine
  html += '<h2 class="section-h">Canonical spine</h2>';
  if (!a.canonical_spine || a.canonical_spine.length === 0) {
    html += '<p style="color:var(--muted);">No canonical spine detected (main screen name doesn\'t match {ACTIVITY}MAIN convention).</p>';
  } else {
    for (const step of a.canonical_spine) {
      html += '<div class="card spine-step">';
      html += `<div class="phase">${step.phase}</div>`;
      html += `<div>`;
      html += `<div class="task">${esc(step.task || '(user fills form)')}</div>`;
      html += `<div class="desc">${esc(step.description)}</div>`;
      if (step.sp_chain?.length) {
        html += '<div class="sp-chain">';
        for (const sp of step.sp_chain) {
          html += `<span class="sp">seq ${sp.sequenceno ?? '?'} · ${esc(sp.spname)}</span>`;
        }
        html += '</div>';
      }
      html += '</div></div>';
    }
  }

  // Splices
  html += '<h2 class="section-h">Splices</h2>';
  const ss = a.splices;
  if (ss?.ui_splices?.length) {
    html += `<h3 style="font-family:'Fraunces',serif; font-size:16px; margin:12px 0 6px; color:var(--purple);">UI splices · ${ss.ui_splices.length}</h3>`;
    for (const s of ss.ui_splices.slice(0, 40)) {
      html += `<div class="splice-card"><div class="label">UI · ${esc(s.splice_id)}</div>`;
      html += `<div>${esc(s.description)}</div>`;
      html += `<div class="trigger">trigger: ${esc(s.trigger)}</div></div>`;
    }
    if (ss.ui_splices.length > 40) html += `<p class="mono" style="color:var(--muted);">…and ${ss.ui_splices.length - 40} more</p>`;
  }
  if (ss?.state_splices?.length) {
    html += `<h3 style="font-family:'Fraunces',serif; font-size:16px; margin:18px 0 6px; color:var(--purple);">State splices · ${ss.state_splices.length}</h3>`;
    for (const s of ss.state_splices.slice(0, 16)) {
      html += `<div class="splice-card"><div class="label">STATE · ${esc(s.splice_id)}</div>`;
      html += `<div class="trigger">trigger: ${esc(s.trigger)} (on service ${esc(s.hook_service)})</div></div>`;
    }
  }
  if (ss?.data_splices?.length) {
    html += `<h3 style="font-family:'Fraunces',serif; font-size:16px; margin:18px 0 6px; color:var(--purple);">Data splices (from SP IF branches) · ${ss.data_splices.length}</h3>`;
    for (const s of ss.data_splices.slice(0, 30)) {
      const cons = s.sp_occurrences?.[0]?.consequences || {};
      let consStr = '';
      if (cons.execs?.length) consStr += `EXEC ${cons.execs.join(', ')}; `;
      if (cons.raiserrors?.length) consStr += `RAISE ${cons.raiserrors.join(', ')}; `;
      if (cons.inserts?.length) consStr += `INSERT ${cons.inserts.join(', ')}; `;
      if (cons.updates?.length) consStr += `UPDATE ${cons.updates.join(', ')}; `;
      html += `<div class="splice-card"><div class="label">DATA · ${esc(s.trigger)}</div>`;
      html += `<div class="trigger">in: ${esc(s.sp_occurrences?.[0]?.sp ?? '')} → ${esc(consStr)}</div></div>`;
    }
    if (ss.data_splices.length > 30) html += `<p class="mono" style="color:var(--muted);">…and ${ss.data_splices.length - 30} more</p>`;
  }

  // Slots
  html += `<h2 class="section-h">Slots per screen</h2>`;
  for (const sc of a.screens) {
    html += `<details style="margin:8px 0;"><summary style="cursor:pointer; padding:10px 14px; background:#faf3df; border:1px solid var(--rule); border-radius:6px;"><b class="mono" style="color:var(--purple);">${esc(sc.ilbo_name)}</b> · ${esc(sc.ilbo_desc)} · ${sc.slot_count} slots</summary>`;
    if (sc.slots?.length) {
      html += '<table class="slots"><tr><th>Field name</th><th>Label</th><th>Type</th><th>Datatype</th><th>Section</th></tr>';
      for (const s of sc.slots.slice(0, 60)) {
        html += `<tr><td class="mono">${esc(s.field_name || s.field_id)}</td>`;
        html += `<td>${esc(s.display_label) || '<span style="color:var(--muted-2);">(no label)</span>'}</td>`;
        html += `<td class="mono">${esc(s.input_type)}</td>`;
        html += `<td class="mono">${esc(s.datatype)}</td>`;
        html += `<td class="mono" style="color:var(--muted);">${esc(s.section)}</td></tr>`;
      }
      html += '</table>';
    }
    html += '</details>';
  }

  // Cross-journey outgoing edges
  const out_edges = (DATA.graph?.edges || []).filter(e => e.from_activity === name);
  if (out_edges.length) {
    html += '<h2 class="section-h">Outgoing cross-journey edges</h2>';
    for (const e of out_edges) {
      html += `<div class="edge-row"><span class="mono">${esc(e.from_activity)}</span> <span class="arrow">→</span> <span class="mono" style="color:var(--purple);">${esc(e.to_activity)}</span> via ${esc(e.via_task)} (${esc(e.label)})</div>`;
    }
  }

  document.getElementById('content').innerHTML = html;
}

init();
