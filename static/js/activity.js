// // ── Activity ──
async function renderActivity(app){
  if(!isAuthenticated()){app.innerHTML='<div class="empty"><h3>🔒 Authentication required</h3><p>Set your API key to view activity log</p></div>';return}
  const params = new URLSearchParams(location.hash.split('?')[1]||'');
  const target_type = params.get('target_type') || '';
  const action = params.get('action') || '';
  
  let url = '/api/activity?limit=100';
  if(target_type) url += `&target_type=${target_type}`;
  if(action) url += `&action=${action}`;
  
  const [data, stats] = await Promise.all([
    api('GET', url),
    api('GET', '/api/activity/stats?days=7')
  ]);
  if(!data) return;
  
  const targetTypes = ['','task','page','comment','project','discussion'];
  const actions = ['','create','update','delete','approved','submitted for review','rejected','started'];
  
  app.innerHTML = `
    <div class="kb-header">
      <h2>📋 Activity</h2>
      <div class="kb-filters">
        <select onchange="location.hash='#activity?target_type='+this.value">
          ${targetTypes.map(t => `<option value="${t}" ${target_type===t?'selected':''}>${t||'All types'}</option>`).join('')}
        </select>
        <select onchange="location.hash='#activity?action='+this.value">
          ${actions.map(a => `<option value="${a}" ${action===a?'selected':''}>${a||'All actions'}</option>`).join('')}
        </select>
      </div>
    </div>
    <div style="padding:0 24px 24px">
      ${stats ? `<div class="stats-bar" style="padding:0 0 16px">
        <div class="stat-card"><div class="stat-val">${stats.total}</div><div class="stat-lbl">Last 7 days</div></div>
        ${(stats.by_action||[]).slice(0,3).map(a => `<div class="stat-card"><div class="stat-val">${a.count}</div><div class="stat-lbl">${esc(a.action)}</div></div>`).join('')}
      </div>` : ''}
      ${data.activity.length === 0 ?
        '<div class="empty"><div class="empty-icon">📋</div><h3>No activity yet</h3><p>Activity is logged when tasks, comments, or projects are created/updated</p></div>' :
        data.activity.map(a => {
          const detail = a.detail || {};
          const icon = {task:'📝',page:'📄',comment:'💬',project:'📂',discussion:'💬'}[a.target_type] || '📌';
          return `<div class="attn-item">
            <span class="attn-dot" style="background:${{create:'var(--ok)',update:'var(--ac)',delete:'var(--err)',approved:'var(--ok)',rejected:'var(--err)'}[a.action]||'var(--t2)'}"></span>
            <span>${icon}</span>
            <div class="attn-info">
              <div class="title"><strong>${esc(a.actor)}</strong> ${esc(a.action)} ${esc(a.target_type)} ${detail.title ? `"${esc(detail.title)}"` : a.target_id}</div>
              <div class="sub">${a.project_name ? esc(a.project_name) + ' · ' : ''}${timeAgo(a.created_at)}</div>
            </div>
          </div>`;
        }).join('')
      }
      ${data.total > 100 ? '<div style="text-align:center;padding:12px;color:var(--t2)">Showing 100 of '+data.total+'</div>' : ''}
    </div>`;
}


// // ── Keyboard shortcuts ──
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){
    if(document.getElementById('modal-bg').classList.contains('open'))closeModal();
    else if(S.taskPanelOpen)closeTaskPanel();
  }
});

// Sidebar key input: Enter to submit
document.addEventListener('DOMContentLoaded',()=>{
  const inp=document.getElementById('sb-key-input');
  if(inp)inp.addEventListener('keydown',e=>{if(e.key==='Enter')sidebarAuth()});
});

// Start
checkHealth();
render();
setInterval(checkHealth,30000);
setInterval(pollInboxBadge,15000);


