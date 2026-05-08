// ── Plans ──

async function renderPlans(app, slug) {
  const statusFilter = new URLSearchParams(location.hash.split('?')[1] || '').get('status') || '';
  let url = slug ? `/api/projects/${slug}/plans` : '/api/plans';
  if (statusFilter) url += `?status=${statusFilter}`;

  const data = await api('GET', url);
  if (!data) return;

  const plans = data.plans || [];
  const statusCfg = {
    proposed:  { icon: '💭', label: 'Proposed',  color: 'var(--ac)' },
    approved:  { icon: '✅', label: 'Approved',  color: 'var(--ok)' },
    executing: { icon: '▶️', label: 'Executing', color: '#f59e0b' },
    done:      { icon: '🏁', label: 'Done',      color: 'var(--t2)' },
    rejected:  { icon: '❌', label: 'Rejected',  color: '#ef4444' },
  };

  // Count by status
  const counts = {};
  plans.forEach(p => { counts[p.status] = (counts[p.status] || 0) + 1; });

  const statusBtns = Object.entries(statusCfg).map(([k, v]) =>
    `<button class="plan-filter-btn ${statusFilter === k ? 'active' : ''}"
       onclick="location.hash='${slug ? '#project/' + slug : ''}/plans?status=${k}'"
       style="--fc:${v.color}">
       ${v.icon} ${v.label}${counts[k] ? ` (${counts[k]})` : ''}
     </button>`
  ).join('');

  app.innerHTML = `
    <div class="kb-header">
      <h2>📋 Plans${slug ? '' : ' (All Projects)'}</h2>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="plan-filter-btn ${!statusFilter ? 'active' : ''}"
           onclick="location.hash='${slug ? '#project/' + slug : ''}/plans'">
          All (${plans.length})
        </button>
        ${statusBtns}
      </div>
      ${slug && isAuthenticated() ? `<button class="btn btn-p btn-sm" onclick="showNewPlanModal('${slug}')">+ New Plan</button>` : ''}
    </div>
    ${slug ? `<div style="padding:0 24px">
      <div style="display:flex;gap:8px;margin-bottom:16px">
        <a href="#project/${slug}/board" class="btn btn-s btn-sm">📋 Board</a>
        <a href="#project/${slug}/tree" class="btn btn-s btn-sm">🌳 Tree</a>
        <span class="btn btn-p btn-sm">📝 Plans</span>
        <a href="#project/${slug}/docs" class="btn btn-s btn-sm">📄 Docs</a>
        ${isAuthenticated() ? `<a href="#project/${slug}/settings" class="btn btn-s btn-sm">⚙️ Settings</a>` : ''}
      </div>
    </div>` : ''}
    <div style="padding:0 24px 24px">
      ${plans.length === 0 ?
        `<div class="empty">
          <div class="empty-icon">📋</div>
          <h3>No plans ${statusFilter ? 'with status "' + statusFilter + '"' : 'yet'}</h3>
          <p>${slug ? 'Create a plan to propose an execution strategy for a mission' : 'Plans are created within individual projects'}</p>
        </div>` :
        `<div class="plans-list">${plans.map(p => _renderPlanCard(p, slug)).join('')}</div>`
      }
    </div>`;
}

function _renderPlanCard(p, slug) {
  const statusCfg = {
    proposed:  { icon: '💭', label: 'Proposed',  color: 'var(--ac)' },
    approved:  { icon: '✅', label: 'Approved',  color: 'var(--ok)' },
    executing: { icon: '▶️', label: 'Executing', color: '#f59e0b' },
    done:      { icon: '🏁', label: 'Done',      color: 'var(--t2)' },
    rejected:  { icon: '❌', label: 'Rejected',  color: '#ef4444' },
  };
  const st = statusCfg[p.status] || { icon: '❓', label: p.status, color: 'var(--t2)' };
  const steps = p.steps || [];
  const stepSummary = steps.length > 0 ?
    `<span style="color:var(--t2);font-size:12px">${steps.length} step${steps.length > 1 ? 's' : ''}</span>` : '';

  return `<div class="plan-card" onclick="showPlanDetail('${p.id}')">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
      <span style="font-size:11px;padding:2px 10px;border-radius:12px;color:#fff;background:${st.color};white-space:nowrap">
        ${st.icon} ${st.label}
      </span>
      ${stepSummary}
      <span style="margin-left:auto;font-size:12px;color:var(--t2)">${timeAgo(p.created_at)}</span>
    </div>
    <div style="font-weight:600;font-size:14px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(p.description)}</div>
    ${p.assignee ? `<div style="font-size:12px;color:var(--t2)">👤 ${esc(p.assignee)}</div>` : ''}
    ${p.mission_id ? `<div style="font-size:12px;color:var(--t2)">🎯 Mission: ${esc(p.mission_id.substring(0, 8))}</div>` : ''}
  </div>`;
}


async function showPlanDetail(id) {
  const data = await api('GET', `/api/plans/${id}`);
  if (!data) return;
  const p = data.plan || data;

  const statusCfg = {
    proposed:  { icon: '💭', label: 'Proposed',  color: 'var(--ac)' },
    approved:  { icon: '✅', label: 'Approved',  color: 'var(--ok)' },
    executing: { icon: '▶️', label: 'Executing', color: '#f59e0b' },
    done:      { icon: '🏁', label: 'Done',      color: 'var(--t2)' },
    rejected:  { icon: '❌', label: 'Rejected',  color: '#ef4444' },
  };
  const st = statusCfg[p.status] || { icon: '❓', label: p.status, color: 'var(--t2)' };
  const steps = p.steps || [];

  // Steps HTML with numbered list
  const stepsHtml = steps.length > 0 ?
    `<div style="margin-top:12px">
      <h4 style="font-size:13px;color:var(--t2);margin-bottom:8px">Steps</h4>
      <ol style="padding-left:20px;font-size:14px;line-height:1.8">
        ${steps.map((s, i) => {
          const text = typeof s === 'string' ? s : (s.text || s.description || JSON.stringify(s));
          return `<li style="margin-bottom:4px">${esc(text)}</li>`;
        }).join('')}
      </ol>
    </div>` :
    '<div style="color:var(--t3);font-size:13px;margin-top:8px">No steps defined</div>';

  // Context section
  const ctxHtml = p.context ?
    `<div style="margin-top:12px">
      <h4 style="font-size:13px;color:var(--t2);margin-bottom:6px">Context</h4>
      <div style="font-size:14px;line-height:1.7;color:var(--t1);white-space:pre-wrap">${md(p.context)}</div>
    </div>` : '';

  // Metadata
  const metaHtml = p.metadata && Object.keys(p.metadata).length > 0 ?
    `<div style="margin-top:12px">
      <h4 style="font-size:13px;color:var(--t2);margin-bottom:6px">Metadata</h4>
      <div style="font-size:13px;color:var(--t1)">${Object.entries(p.metadata).map(([k, v]) =>
        `<span style="display:inline-block;background:var(--bg2);border:1px solid var(--bd);border-radius:var(--rs);padding:2px 8px;margin:2px 4px 2px 0">
          <span style="color:var(--t2)">${esc(k)}</span>: ${esc(String(v))}
        </span>`
      ).join('')}</div>
    </div>` : '';

  // Action buttons based on status
  let actions = '';
  if (isAuthenticated()) {
    const canApprove = p.status === 'proposed';
    const canReject = p.status === 'proposed';
    const canExecute = p.status === 'approved';
    const canComplete = p.status === 'executing';
    const canDelete = p.status === 'proposed' || p.status === 'rejected';

    if (canApprove || canReject || canExecute || canComplete) {
      actions += `<div style="margin-top:16px;padding-top:12px;border-top:1px solid var(--bd);display:flex;gap:8px;flex-wrap:wrap">`;
      if (canApprove)
        actions += `<button class="btn btn-p btn-sm" onclick="event.stopPropagation();planAction('${p.id}','approve')">✅ Approve</button>`;
      if (canReject)
        actions += `<button class="btn btn-sm" style="background:#ef4444" onclick="event.stopPropagation();planAction('${p.id}','reject')">❌ Reject</button>`;
      if (canExecute)
        actions += `<button class="btn btn-p btn-sm" style="background:#f59e0b" onclick="event.stopPropagation();planAction('${p.id}','execute')">▶️ Execute</button>`;
      if (canComplete)
        actions += `<button class="btn btn-p btn-sm" style="background:var(--ok)" onclick="event.stopPropagation();planAction('${p.id}','complete')">🏁 Complete</button>`;
      actions += `</div>`;
    }
    if (canDelete) {
      actions += `<div style="margin-top:8px;display:flex;gap:8px">
        <button class="btn btn-sm" style="color:#ef4444" onclick="event.stopPropagation();deletePlan('${p.id}')">🗑️ Delete</button>
      </div>`;
    }
  }

  // Mission link
  const missionLink = p.mission_id ?
    `<span style="font-size:13px">🎯 Mission: <a href="javascript:void(0)" onclick="event.stopPropagation();loadAndOpenTask('${p.mission_id}')" style="color:var(--ac);text-decoration:none">${esc(p.mission_id.substring(0, 8))}</a></span>` : '';

  openModal(`
    <div style="max-width:560px;padding:24px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <span style="font-size:20px">${st.icon}</span>
        <h3 style="margin:0;flex:1">Plan ${p.id.substring(0, 8)}</h3>
        <span style="font-size:12px;padding:3px 10px;border-radius:12px;color:#fff;background:${st.color}">${st.label}</span>
        <button onclick="closeModal()" style="background:none;border:none;color:var(--t2);cursor:pointer;font-size:18px;padding:4px 8px">✕</button>
      </div>

      <div style="font-size:15px;line-height:1.7;font-weight:600;margin-bottom:12px;white-space:pre-wrap">${md(p.description)}</div>

      <div style="display:flex;gap:16px;font-size:13px;color:var(--t2);flex-wrap:wrap">
        ${p.assignee ? `<span>👤 ${esc(p.assignee)}</span>` : ''}
        ${missionLink}
        <span>📅 ${timeAgo(p.created_at)}</span>
        ${p.updated_at && p.updated_at !== p.created_at ? `<span>Updated ${timeAgo(p.updated_at)}</span>` : ''}
        <span>Created by ${esc(p.created_by || 'owner')}</span>
      </div>

      ${stepsHtml}
      ${ctxHtml}
      ${metaHtml}
      ${actions}
    </div>
  `);
}


async function showNewPlanModal(slug) {
  openModal(`
    <div style="max-width:520px;padding:24px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <h3 style="margin:0">New Plan</h3>
        <span style="font-size:12px;color:var(--t2)">for ${esc(slug)}</span>
        <button onclick="closeModal()" style="margin-left:auto;background:none;border:none;color:var(--t2);cursor:pointer;font-size:18px;padding:4px 8px">✕</button>
      </div>
      <div class="field">
        <label>Description *</label>
        <textarea id="plan-desc" rows="3" placeholder="What is this plan about?" style="width:100%;padding:8px 12px;border:1px solid var(--bd);border-radius:var(--rs);background:var(--bg1);color:var(--t1);font-size:14px;resize:vertical"></textarea>
      </div>
      <div class="field">
        <label>Assignee</label>
        <input id="plan-assignee" type="text" placeholder="Who will execute this?" style="width:100%;padding:8px 12px;border:1px solid var(--bd);border-radius:var(--rs);background:var(--bg1);color:var(--t1);font-size:14px">
      </div>
      <div class="field">
        <label>Steps (one per line)</label>
        <textarea id="plan-steps" rows="5" placeholder="Step 1: Do this&#10;Step 2: Then this&#10;Step 3: Finally this" style="width:100%;padding:8px 12px;border:1px solid var(--bd);border-radius:var(--rs);background:var(--bg1);color:var(--t1);font-size:14px;resize:vertical"></textarea>
      </div>
      <div class="field">
        <label>Context (optional)</label>
        <textarea id="plan-context" rows="3" placeholder="Background information, constraints, etc." style="width:100%;padding:8px 12px;border:1px solid var(--bd);border-radius:var(--rs);background:var(--bg1);color:var(--t1);font-size:14px;resize:vertical"></textarea>
      </div>
      <div style="display:flex;gap:8px;margin-top:16px">
        <button class="btn btn-p" onclick="createPlan('${slug}')">Create Plan</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
      </div>
    </div>
  `);
  setTimeout(() => document.getElementById('plan-desc')?.focus(), 100);
}


async function createPlan(slug) {
  const desc = document.getElementById('plan-desc')?.value?.trim();
  if (!desc) { toast('Description is required', 'error'); return; }

  const stepsRaw = document.getElementById('plan-steps')?.value || '';
  const steps = stepsRaw.split('\n').map(s => s.trim()).filter(Boolean);

  const payload = {
    description: desc,
    steps: steps.length > 0 ? steps : undefined,
    assignee: document.getElementById('plan-assignee')?.value?.trim() || undefined,
    context: document.getElementById('plan-context')?.value?.trim() || undefined,
  };

  const result = await api('POST', `/api/projects/${slug}/plans`, payload);
  if (!result) return;

  toast('Plan created', 'ok');
  closeModal();
  render();
}


async function planAction(id, action) {
  const btn = event.target.closest('button');
  if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }

  const result = await api('POST', `/api/plans/${id}/${action}`);
  if (!result) {
    if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
    return;
  }

  toast(`Plan ${action}d`, 'ok');
  // Refresh the modal content
  showPlanDetail(id);
}


async function deletePlan(id) {
  if (!confirm('Delete this plan? This cannot be undone.')) return;

  const result = await api('DELETE', `/api/plans/${id}`);
  if (!result) return;

  toast('Plan deleted', 'ok');
  closeModal();
  render();
}
