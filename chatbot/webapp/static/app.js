// Ramco PO chatbot — interactive test UI

let sessionId = null;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function api(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  return await res.json();
}

async function resetSession() {
  const r = await api('/reset', {session_id: sessionId});
  sessionId = r.session_id;
  $('#messages').innerHTML = `
    <div class="msg msg-system">
      <div class="msg-body">
        <p>Fresh session. Send a message to start.</p>
      </div>
    </div>`;
  $('#trace-stream').innerHTML = '';
  $('#trace-empty').style.display = 'block';
  $('#status-text').textContent = 'Bot v8 · 70% eval pass · idle';
}

function appendMessage(kind, text) {
  const wrap = document.createElement('div');
  wrap.className = `msg msg-${kind}`;
  wrap.innerHTML = `<div class="msg-body"><p>${esc(text).replace(/\n/g, '<br>')}</p></div>`;
  $('#messages').appendChild(wrap);
  $('#messages').scrollTop = $('#messages').scrollHeight;
}

function renderChip(label, kind = '') {
  return `<span class="chip ${kind}">${esc(label)}</span>`;
}

function renderTrace(turn) {
  $('#trace-empty').style.display = 'none';
  const t = turn.trace;
  const card = document.createElement('div');
  card.className = 'trace-card';

  let html = '';
  html += `<div class="turn-elapsed">${turn.elapsed_ms}ms</div>`;
  html += `<div class="turn-label">Turn ${turn.turn}</div>`;
  html += `<div class="turn-user">"${esc(turn.user)}"</div>`;

  const rowsHtml = [
    ['Intent', t.intent
      ? renderChip(t.intent, 'purple')
      : '<span class="value empty">none</span>'],
    ['Journey locked', t.journey_locked
      ? renderChip(t.journey_locked, 'purple bold')
      : (t.journey_candidates && t.journey_candidates.length
         ? `candidates: ${t.journey_candidates.map(c => renderChip(c)).join('')}`
         : '<span class="value empty">none</span>')],
    ['Slots this turn', Object.keys(t.slots_extracted_this_turn || {}).length
      ? Object.entries(t.slots_extracted_this_turn).map(([k, v]) =>
          `<div class="kv"><span class="k">${esc(k)}</span>: <span class="v">${esc(JSON.stringify(v))}</span></div>`
        ).join('')
      : '<span class="value empty">none</span>'],
    ['All slots in state', Object.keys(t.all_slots_in_state || {}).length
      ? Object.entries(t.all_slots_in_state).map(([k, v]) =>
          renderChip(`${k}=${JSON.stringify(v)}`)
        ).join('')
      : '<span class="value empty">empty</span>'],
    ['Splice triggered', t.splice_triggered
      ? renderChip(t.splice_triggered, 'terra')
      : '<span class="value empty">none</span>'],
    ['Splices walked', (t.splices_walked || []).length
      ? t.splices_walked.map(s => renderChip(s, 'terra')).join('')
      : '<span class="value empty">none</span>'],
    ['Required slots (splice)', (t.additional_required_slots || []).length
      ? t.additional_required_slots.map(s => renderChip(s)).join('')
      : '<span class="value empty">none</span>'],
    ['Validation error', t.validation_error_detected
      ? renderChip('YES', 'red')
      : '<span class="value empty">no</span>'],
  ];
  rowsHtml.forEach(([label, val]) => {
    html += `<div class="trace-row"><div class="label">${label}</div><div class="value">${val}</div></div>`;
  });

  // v8 step-aware overlay: current collect-step + mandatory progress (decorative only)
  if (t.current_step) {
    const cs = t.current_step;
    const mp = t.mandatory_progress || {filled: 0, total: 0};
    html += `<div class="trace-row"><div class="label">Current step</div><div class="value">`;
    html += renderChip(`S${cs.step}: ${esc(cs.caption)}`, 'gold bold');
    if (cs.is_grid) html += renderChip('LINE LOOP', 'red');
    html += ` <span class="muted" style="font-size:10px;">${cs.slot_count} slots · ${mp.filled}/${mp.total} mandatory</span>`;
    html += `</div></div>`;
  }

  // TRANS details
  if (t.trans_details && t.trans_details.length) {
    html += `<div class="trace-row"><div class="label">TRANS fired</div><div class="value">`;
    for (const td of t.trans_details) {
      const kindCls = td.kind === 'write' ? 'red' : (td.kind === 'read' ? 'green' : '');
      html += `<div style="margin-bottom: 10px;">`;
      html += renderChip(td.task, `${kindCls} bold`) + ` ` + renderChip(td.kind);
      if (td.activity)  html += ` <span class="muted" style="font-size:10px;">(${esc(td.activity)} / ${esc(td.ui || '?')})</span>`;
      if (td.sp_chain && td.sp_chain.length) {
        html += `<div class="sp-list">`;
        for (const sp of td.sp_chain) {
          html += `<div class="sp-row"><span class="sp-seq">${sp.seq ?? '?'}</span>`;
          html += `<div><span class="sp-name">${esc(sp.sp_name)}</span> <span class="muted" style="font-size:10px;">${sp.branches} branches</span>`;
          if (sp.tables && sp.tables.length) {
            html += `<div class="sp-tables">→ ${sp.tables.join(', ')}</div>`;
          }
          html += `</div></div>`;
        }
        html += `</div>`;
      }
      html += `</div>`;
    }
    html += `</div></div>`;
  }

  // Post-commit context (v7+): if a write commit fired earlier, this drives
  // the journey-switch detection for change-language follow-ups
  if (t.post_commit_context) {
    const pcc = t.post_commit_context;
    html += `<div class="trace-row"><div class="label">Post-commit ctx</div><div class="value">`;
    html += renderChip(pcc.entity_kind, 'green') + ' ';
    html += `<span class="kv"><span class="k">${esc(pcc.id_slot)}</span>=<span class="v">${esc(pcc.entity_id)}</span></span><br/>`;
    html += `<span class="muted" style="font-size:10px;">produced by ${esc(pcc.produced_by)} turn ${pcc.turn} · amend journey: ${esc(pcc.amend_journey || 'n/a')}</span>`;
    html += `</div></div>`;
  }

  // Session entities (memory of produced entities for cross-journey carry)
  if (t.session_entities && t.session_entities.length) {
    html += `<div class="trace-row"><div class="label">Session memory</div><div class="value">`;
    for (const e of t.session_entities) {
      html += `<div class="kv">`;
      html += renderChip(e.kind, 'green');
      html += ` <span class="k">${esc(e.id_slot)}</span>=<span class="v">${esc(e.synthetic_id)}</span>`;
      html += ` <span class="muted" style="font-size:10px;">(from ${esc(e.produced_by)} turn ${e.turn})</span>`;
      html += `</div>`;
    }
    html += `</div></div>`;
  }

  // Files referenced — button to open popup
  if (turn.files_referenced && turn.files_referenced.length) {
    html += `<button class="files-btn" data-turn-idx="${turn.turn}">▸ ${turn.files_referenced.length} files referenced</button>`;
  }

  card.innerHTML = html;

  // Wire up the files button
  if (turn.files_referenced) {
    card._files = turn.files_referenced;
    setTimeout(() => {
      const btn = card.querySelector('.files-btn');
      if (btn) btn.addEventListener('click', () => openFilesPopup(turn.files_referenced));
    }, 0);
  }

  $('#trace-stream').appendChild(card);
  $('#trace-pane').scrollTop = $('#trace-pane').scrollHeight;
}

function openFilesPopup(files) {
  const body = $('#popup-body');
  body.innerHTML = files.map(f => `
    <div class="file-entry">
      <div class="path">${esc(f.path)}</div>
      <div class="why">${esc(f.why)}</div>
    </div>
  `).join('');
  $('#popup-backdrop').classList.add('open');
}

function closePopup() { $('#popup-backdrop').classList.remove('open'); }
function closeScenarios() { $('#scenarios-backdrop').classList.remove('open'); }

async function send() {
  const msg = $('#composer-input').value.trim();
  if (!msg) return;
  if (!sessionId) await resetSession();
  $('#composer-input').value = '';
  $('#composer-input').style.height = 'auto';
  appendMessage('user', msg);
  $('#composer-send').disabled = true;
  $('#status-text').textContent = 'Bot v8 · thinking…';
  try {
    const r = await api('/chat', {session_id: sessionId, message: msg});
    if (r.error) {
      appendMessage('error', '❌ ' + r.error);
    } else {
      appendMessage('bot', r.bot);
      renderTrace(r);
      $('#status-text').textContent = `Bot v8 · ${r.trace.journey_locked ?? 'no journey'} · turn ${r.turn}`;
    }
  } catch (e) {
    appendMessage('error', '❌ ' + e.message);
  } finally {
    $('#composer-send').disabled = false;
  }
}

function loadScenarios() {
  fetch('/static/scenarios.json').then(r => r.json()).then(scenarios => {
    const body = $('#scenarios-body');
    body.innerHTML = scenarios.map((s, i) => `
      <div class="scenario">
        <h3>${i+1}. ${esc(s.title)}</h3>
        <div class="scenario-meta">covers: ${esc(s.covers || '')} · difficulty: ${esc(s.difficulty || 'medium')}</div>
        <div class="scenario-context">${esc(s.context)}</div>
        <div class="turn-list">
          ${s.turns.map((t, j) => `<div class="turn-item" data-n="${j+1}">${esc(t)}</div>`).join('')}
        </div>
        ${s.check && s.check.length ? `
          <div class="check-list">
            <div class="check-list-label">What to check</div>
            ${s.check.map(c => `<div class="check-item">${esc(c)}</div>`).join('')}
          </div>
        ` : ''}
      </div>
    `).join('');
  });
}

// ── Wiring ───────────────────────────────────────────────────────────────
$('#composer').addEventListener('submit', (e) => { e.preventDefault(); send(); });
$('#composer-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});
$('#composer-input').addEventListener('input', (e) => {
  e.target.style.height = 'auto';
  e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
});
$('#btn-reset').addEventListener('click', resetSession);
$('#btn-scenarios').addEventListener('click', () => {
  $('#scenarios-backdrop').classList.add('open');
});
$('#popup-close').addEventListener('click', closePopup);
$('#scenarios-close').addEventListener('click', closeScenarios);
$('#popup-backdrop').addEventListener('click', (e) => {
  if (e.target === $('#popup-backdrop')) closePopup();
});
$('#scenarios-backdrop').addEventListener('click', (e) => {
  if (e.target === $('#scenarios-backdrop')) closeScenarios();
});

// Init
resetSession();
loadScenarios();
