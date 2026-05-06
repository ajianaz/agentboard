// // ── Project Settings ──
async function renderProjectSettings(app,slug){
  if(!isAuthenticated()){app.innerHTML='<div class="empty"><h3>🔒 Authentication required</h3><p>Set your API key to access project settings</p></div>';return}
  const data=await api('GET','/api/projects/'+slug);
  if(!data){app.innerHTML='<div class="empty"><h3>Project not found</h3></div>';return}
  const p=data.project||data;
  const isPublic=p.visibility!=='hidden';
  let h=`<div class="settings-wrap"><h2>${p.icon||'📋'} ${esc(p.name)}</h2>
    <div class="form-group"><label>Visibility</label>
      <div class="vis-toggle" onclick="toggleProjectVisibility('${slug}','${p.visibility||'public'}')">
        <div class="vis-sw ${isPublic?'on':''}"></div>
        <div><div class="vis-label">${isPublic?'👁️ Public':'🚫 Hidden'}</div><div class="vis-sublabel">${isPublic?'Visible to everyone':'Only visible when authenticated'}</div></div>
      </div>
    </div>
    <div class="form-group"><label>Name</label><input id="ps-name" value="${esc(p.name)}"></div>
    <div class="form-group"><div class="field-row"><div><label>Icon (emoji)</label><input class="icon-inp" id="ps-icon" value="${esc(p.icon||'')}"></div><div><label>Color</label><input class="color-inp" id="ps-color" type="color" value="${p.color||'#3b82f6'}"></div></div></div>
    <div class="form-group"><label>Description</label><textarea id="ps-desc" rows="3">${esc(p.description||'')}</textarea></div>
    <div class="form-group"><label>Tags (comma-separated)</label><input id="ps-tags" value="${esc((p.tags||[]).join(', '))}"></div>
    <button class="btn btn-p" onclick="saveProject('${slug}')">Save Changes</button>
    <div class="danger-zone">
      <h4 style="font-size:13px;font-weight:600;margin-bottom:10px;color:var(--t1)">Data</h4>
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <button class="btn btn-s btn-sm" onclick="exportProject('${slug}')">📥 Export Project</button>
        <button class="btn btn-s btn-sm" onclick="exportAll()">📥 Export All</button>
        <button class="btn btn-s btn-sm" onclick="doImport()">📤 Import</button>
      </div>
      <h4 style="font-size:13px;font-weight:600;margin-bottom:10px;color:var(--t1)">Danger</h4>
      <button class="btn btn-d btn-sm" onclick="archiveProject('${slug}')">${p.is_archived?'Unarchive':'Archive'} Project</button>
    </div>
  </div>`;
  app.innerHTML=h;
}
async function saveProject(slug){
  const body={
    name:document.getElementById('ps-name').value,
    icon:document.getElementById('ps-icon').value,
    color:document.getElementById('ps-color').value,
    description:document.getElementById('ps-desc').value,
    tags:document.getElementById('ps-tags').value.split(',').map(t=>t.trim()).filter(Boolean)
  };
  await api('PATCH','/api/projects/'+slug,body);
  toast('Project saved','ok');
  setTimeout(()=>render(),200);
}
async function archiveProject(slug){
  const data=await api('GET','/api/projects/'+slug);
  const p=data?.project||data;
  if(p.is_archived)await api('POST','/api/projects/'+slug+'/restore');
  else await api('DELETE','/api/projects/'+slug);
  toast('Project updated','ok');
  location.hash='#overview';
  setTimeout(()=>render(),200);
}


// // ── Agents ──
async function renderAgents(app){
  const data=await api('GET','/api/agents');
  const agents=data?.agents||[];
  let h=`<div style="padding:24px 24px 0;display:flex;justify-content:space-between;align-items:center"><h2 style="font-size:18px;font-weight:600">🤖 Agents</h2>${isAuthenticated()?'<button class="btn btn-p btn-sm" onclick="showNewAgent()">+ Register Agent</button>':''}</div>`;
  h+=`<div class="agents-grid">`;
  if(!agents.length)h+=`<div class="empty" style="grid-column:1/-1"><div class="empty-icon">🤖</div><h3>No agents registered</h3><p>Register an agent to start assigning tasks</p></div>`;
  agents.forEach(a=>{
    h+=`<div class="agent-card">
      <div class="agent-card-hdr"><div class="agent-avatar" style="background:${a.color||'var(--bg3)'}">${a.avatar||'🤖'}</div><div><div class="agent-name">${esc(a.name||a.id)}</div><div class="agent-role">${esc(a.role||'Agent')}</div></div></div>
      <div class="agent-wl" id="wl-${a.id}">Loading…</div>
    </div>`;
  });
  h+=`</div>`;
  app.innerHTML=h;
  // Load workloads
  agents.forEach(async a=>{
    const wl=await api('GET','/api/agents/'+a.id+'/workload');
    const el=document.getElementById('wl-'+a.id);
    if(!el||!wl)return;
    const parts=[];
    if(wl.total)parts.push(`Total: ${wl.total}`);
    if(wl.completed)parts.push(`Done: ${wl.completed}`);
    if(wl.active_projects?.length)parts.push(`Projects: ${wl.active_projects.map(p=>p.name||p).join(', ')}`);
    el.innerHTML=parts.map(p=>`<span>${p}</span>`).join('');
  });
}
function showNewAgent(){
  openModal(`<h3>Register Agent</h3>
    <div class="form-group"><label>ID (unique identifier)</label><input id="na-id" placeholder="e.g. content-writer"></div>
    <div class="form-group"><label>Display Name</label><input id="na-name" placeholder="e.g. Content Writer"></div>
    <div class="form-group"><label>Role</label><input id="na-role" placeholder="e.g. Content Writer"></div>
    <div class="form-group"><div class="field-row"><div><label>Avatar (emoji)</label><input class="icon-inp" id="na-avatar" value="🤖"></div><div><label>Color</label><input class="color-inp" id="na-color" type="color" value="#3b82f6"></div></div></div>
    <div style="display:flex;gap:8px;justify-content:flex-end"><button class="btn btn-s" onclick="closeModal()">Cancel</button><button class="btn btn-p" onclick="createAgent()">Register</button></div>`);
}
async function createAgent(){
  const id=document.getElementById('na-id').value.trim();
  if(!id){toast('Agent ID required','err');return}
  await api('POST','/api/agents',{
    id,
    name:document.getElementById('na-name').value||id,
    role:document.getElementById('na-role').value,
    avatar:document.getElementById('na-avatar').value,
    color:document.getElementById('na-color').value
  });
  closeModal();toast('Agent registered','ok');
  setTimeout(()=>render(),200);
}


// // ── System Settings ──
async function renderSystemSettings(app){
  if(!isAuthenticated()){app.innerHTML='<div class="empty"><h3>🔒 Authentication required</h3><p>Set your API key to access settings</p></div>';return}
  let h=`<div class="settings-wrap" style="max-width:700px"><h2>⚙️ System Settings</h2>`;
  // API Keys section
  h+=`<div style="margin-bottom:24px"><h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:var(--t1)">🔑 API Keys</h3>`;
  h+=`<div id="keys-list" style="margin-bottom:12px">Loading…</div>`;
  h+=`<button class="btn btn-p btn-sm" onclick="showNewKeyModal()">+ Generate New Key</button>`;
  h+=`</div>`;
  // Maintenance section
  h+=`<div style="margin-bottom:24px"><h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:var(--t1)">🔧 Maintenance Mode</h3>`;
  h+=`<p style="font-size:12px;color:var(--t2);margin-bottom:8px">When enabled, all write operations return 503. Read operations continue normally.</p>`;
  h+=`<div id="maint-status">Loading…</div>`;
  h+=`<div style="display:flex;gap:8px;margin-top:8px">`;
  h+=`<button class="btn btn-d btn-sm" onclick="toggleMaintenance(true)">Enable Maintenance</button>`;
  h+=`<button class="btn btn-p btn-sm" onclick="toggleMaintenance(false)">Disable Maintenance</button>`;
  h+=`</div></div>`;
  h+=`</div>`;
  app.innerHTML=h;
  loadKeys();
  loadMaintStatus();
}
async function loadKeys(){
  const data=await api('GET','/api/auth/keys');
  const el=document.getElementById('keys-list');
  if(!el)return;
  if(!data||!data.keys||!data.keys.length){el.innerHTML='<p style="font-size:12px;color:var(--t2)">No API keys found</p>';return}
  el.innerHTML=data.keys.map(k=>{
    const status=k.is_active?'<span style="color:#22c55e">● Active</span>':(k.grace_until?'<span style="color:#f59e0b">● Grace Period</span>':'<span style="color:#6b7280">● Inactive</span>');
    const masked=k.id.slice(0,4)+'****'+k.id.slice(-4);
    return`<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--bd)">
      <div><div style="font-size:13px;font-weight:500">${esc(k.label)} <span style="font-size:11px;color:var(--t2)">${masked}</span></div><div style="font-size:11px;color:var(--t2)">${status} · Created ${fmtTime(k.created_at)}${k.last_used_at?' · Used '+fmtTime(k.last_used_at):''}</div></div>
      <div style="display:flex;gap:4px">${k.is_active?`<button class="btn btn-s btn-sm" onclick="deactivateKey('${k.id}')">Deactivate</button>`:`<button class="btn btn-s btn-sm" onclick="activateKey('${k.id}')">Activate</button>`}<button class="btn btn-d btn-sm" onclick="deleteKey('${k.id}')">Delete</button></div>
    </div>`;
  }).join('');
}
function showNewKeyModal(){
  openModal(`<h3>Generate API Key</h3>
    <div class="form-group"><label>Label</label><input id="nk-label" placeholder="e.g. claude-code, ci-bot"></div>
    <p style="font-size:12px;color:var(--t2);margin-bottom:12px">The raw key will be shown <strong>once</strong> after creation. Save it securely.</p>
    <div style="display:flex;gap:8px;justify-content:flex-end"><button class="btn btn-s" onclick="closeModal()">Cancel</button><button class="btn btn-p" onclick="createKey()">Generate</button></div>`);
}
async function createKey(){
  const label=document.getElementById('nk-label').value.trim()||'generated';
  const data=await api('POST','/api/auth/keys',{label});
  if(!data){toast('Failed to create key','err');return}
  closeModal();
  openModal(`<h3>🔑 New API Key</h3>
    <div class="form-group"><label>Save this key now — it cannot be retrieved again!</label><input id="new-key-raw" value="${esc(data.key)}" readonly style="font-family:monospace;font-size:13px"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end"><button class="btn btn-s" onclick="navigator.clipboard.writeText(document.getElementById('new-key-raw').value);toast('Copied!','ok')">📋 Copy</button><button class="btn btn-p" onclick="closeModal();loadKeys()">Done</button></div>`);
  loadKeys();
}
async function deactivateKey(id){
  const grace=prompt('Grace period in minutes (blank = 0, key stops immediately):','5');
  const mins=grace?parseInt(grace):0;
  await api('PATCH','/api/auth/keys/'+id,{deactivate:true,grace_minutes:mins});
  toast('Key deactivated','ok');loadKeys();
}
async function activateKey(id){
  await api('PATCH','/api/auth/keys/'+id,{is_active:true});
  toast('Key activated','ok');loadKeys();
}
async function deleteKey(id){
  if(!confirm('Permanently delete this API key? This cannot be undone.'))return;
  await api('DELETE','/api/auth/keys/'+id);
  toast('Key deleted','ok');loadKeys();
}
async function loadMaintStatus(){
  const data=await api('GET','/api/health');
  const el=document.getElementById('maint-status');
  if(!el)return;
  if(!data){el.innerHTML='Failed to load status';return}
  el.innerHTML=data.maintenance?'<span style="color:#ef4444;font-weight:500;font-size:13px">⚠️ Maintenance mode is ACTIVE</span>':'<span style="color:#22c55e;font-size:13px">✅ System operating normally</span>';
}
async function toggleMaintenance(enable){
  // ⚠️ Intentional: maintenance is config-only (TOML or AGENTBOARD_MAINTENANCE env).
  // No API toggle exists — this prevents accidental lockout and ensures the change
  // is persistent across restarts. See architecture decision in PR #60.
  toast('Maintenance mode is controlled via config (TOML or AGENTBOARD_MAINTENANCE env). Restart server to apply changes.','info');
}


// // ── Public Dashboard (unauthenticated visitors) ──
async function renderPublicDashboard(app){
  const data=await api('GET','/api/stats/public');
  if(!data){app.innerHTML='<div class="empty"><div class="empty-icon">📊</div><h3>Unable to load dashboard</h3><p>The server may be starting up or unavailable</p></div>';return}
  const agents=data.agents||[];
  const projects=data.projects||[];
  const st=data.status_totals||{};
  const act=data.recent_activity||{};
  const total=st.total||1;
  let h=`<div class="pub-wrap">`;
  // Hero
  h+=`<div class="pub-hero"><h1>Agent<span>Board</span></h1><p>Team Dashboard — Public Overview</p></div>`;
  // Quick stats
  h+=`<div class="pub-stats">`;
  h+=`<div class="pub-stat"><div class="pub-stat-val" style="color:var(--ac)">${st.total||0}</div><div class="pub-stat-lbl">Total Tasks</div></div>`;
  h+=`<div class="pub-stat"><div class="pub-stat-val" style="color:var(--ok)">${st.done||0}</div><div class="pub-stat-lbl">Done</div></div>`;
  h+=`<div class="pub-stat"><div class="pub-stat-val" style="color:var(--rev)">${st.review||0}</div><div class="pub-stat-lbl">Review</div></div>`;
  h+=`<div class="pub-stat"><div class="pub-stat-val" style="color:var(--ac)">${st.in_progress||0}</div><div class="pub-stat-lbl">In Progress</div></div>`;
  h+=`<div class="pub-stat"><div class="pub-stat-val" style="color:#6b7280">${st.todo||0}</div><div class="pub-stat-lbl">To Do</div></div>`;
  h+=`<div class="pub-stat"><div class="pub-stat-val" style="color:var(--warn)">${st.proposed||0}</div><div class="pub-stat-lbl">Proposed</div></div>`;
  h+=`</div>`;
  // Status Breakdown — horizontal stacked bar
  const segments=[
    {key:'done',label:'Done',color:'var(--ok)',count:st.done||0},
    {key:'in_progress',label:'In Progress',color:'var(--ac)',count:st.in_progress||0},
    {key:'review',label:'Review',color:'var(--rev)',count:st.review||0},
    {key:'todo',label:'To Do',color:'#6b7280',count:st.todo||0},
    {key:'proposed',label:'Proposed',color:'var(--warn)',count:st.proposed||0}
  ];
  h+=`<div class="pub-section"><div class="pub-section-title">Status Breakdown</div>`;
  h+=`<div class="pub-stacked-wrap"><div class="pub-stacked-bar">`;
  segments.forEach(s=>{
    const pct=(s.count/total*100).toFixed(1);
    if(s.count>0)h+=`<div class="pub-stacked-seg" style="width:${pct}%;background:${s.color}" title="${s.label}: ${s.count}"></div>`;
  });
  h+=`</div><div class="pub-legend">`;
  segments.forEach(s=>{
    h+=`<div class="pub-legend-item"><div class="pub-legend-dot" style="background:${s.color}"></div>${s.label} (${s.count})</div>`;
  });
  h+=`</div></div></div>`;
  // Agent Cards Grid
  h+=`<div class="pub-section"><div class="pub-section-title">🤖 Agents (${agents.length})</div>`;
  if(agents.length){
    h+=`<div class="pub-agent-grid">`;
    agents.forEach(a=>{
      const pct=a.completion_pct||0;
      const pctColor=pct>=70?'var(--ok)':pct>=40?'var(--warn)':'var(--err)';
      h+=`<div class="pub-agent-card">`;
      h+=`<div class="pub-agent-name"><span class="pub-agent-emoji">${esc(a.avatar||'🤖')}</span>${esc(a.name)}</div>`;
      h+=`<div class="pub-agent-count">${a.done}/${a.total} tasks · <span style="color:${pctColor};font-weight:600">${pct}%</span></div>`;
      h+=`<div class="pub-bar"><div class="pub-bar-fill" style="width:${pct}%;background:${pctColor}"></div></div>`;
      h+=`<div class="pub-badges">`;
      if(a.in_progress)h+=`<span class="pub-badge pub-badge-progress">🔄 ${a.in_progress} active</span>`;
      if(a.proposed)h+=`<span class="pub-badge pub-badge-proposed">💡 ${a.proposed} proposed</span>`;
      if(a.done)h+=`<span class="pub-badge pub-badge-done">✓ ${a.done} done</span>`;
      h+=`</div></div>`;
    });
    h+=`</div>`;
  }else{h+=`<div class="pub-empty">No agent data available</div>`}
  h+=`</div>`;
  // Project Progress
  h+=`<div class="pub-section"><div class="pub-section-title">📂 Projects (${projects.length})</div>`;
  if(projects.length){
    h+=`<div class="pub-project-list">`;
    projects.forEach(p=>{
      const pct=p.completion_pct||0;
      const pctColor=pct>=70?'var(--ok)':pct>=40?'var(--warn)':'var(--ac)';
      h+=`<div class="pub-project-item">`;
      h+=`<div class="pub-project-hdr"><span class="pub-project-icon">${p.icon||'📋'}</span><span class="pub-project-name">${esc(p.name)}</span><span class="pub-project-pct" style="color:${pctColor}">${pct}%</span></div>`;
      h+=`<div class="pub-bar"><div class="pub-bar-fill" style="width:${pct}%;background:${pctColor}"></div></div>`;
      h+=`<div style="display:flex;justify-content:space-between;font-size:12px;color:var(--t2)"><span>${p.done}/${p.total} tasks</span></div>`;
      h+=`</div>`;
    });
    h+=`</div>`;
  }else{h+=`<div class="pub-empty">No project data available</div>`}
  h+=`</div>`;
  // Recent Activity
  h+=`<div class="pub-section"><div class="pub-section-title">📊 Recent Activity</div>`;
  h+=`<div class="pub-activity"><span class="pub-activity-icon">📈</span>`;
  h+=`<div class="pub-activity-text"><strong>${act.last_7_days||0}</strong> actions in the last 7 days · <strong>${act.last_30_days||0}</strong> in the last 30 days</div>`;
  h+=`</div></div>`;
  // Auth hint
  h+=`<div class="pub-auth-hint"><p>🔒 <a href="#" onclick="document.getElementById('sb-key-input').focus();document.getElementById('sb-key-input').scrollIntoView({behavior:'smooth',block:'center'});return false">Sign in with an API key</a> for full access to boards, agents, and analytics.</p></div>`;
  h+=`</div>`;
  app.innerHTML=h;
}


// // ── Export/Import ──
async function exportProject(slug){
  const data=await api('GET','/api/export?project='+slug);
  if(!data)return;
  downloadJSON(data,'agentboard-'+slug+'.json');
  toast('Exported!','ok');
}
async function exportAll(){
  const data=await api('GET','/api/export');
  if(!data)return;
  downloadJSON(data,'agentboard-export.json');
  toast('Exported all!','ok');
}
function downloadJSON(data,filename){
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download=filename;a.click();
  URL.revokeObjectURL(url);
}
function doImport(){
  const input=document.createElement('input');input.type='file';input.accept='.json';
  input.onchange=async e=>{
    const file=e.target.files[0];if(!file)return;
    try{
      const text=await file.text();
      const data=JSON.parse(text);
      const result=await api('POST','/api/import',{data});
      if(result)toast('Imported: '+JSON.stringify(result.imported),'ok');
    }catch(err){toast('Invalid file','err')}
  };
  input.click();
}


// // ── Analytics ──
async function renderAnalytics(app){
  if(!isAuthenticated()){app.innerHTML='<div class="empty"><h3>🔒 Authentication required</h3><p>Set your API key to view analytics</p></div>';return}
  const days = new URLSearchParams(location.hash.split('?')[1]).get('days') || '7';
  const [agentData, trendData] = await Promise.all([
    api('GET', `/api/analytics/agents?days=${days}`),
    api('GET', `/api/analytics/trends?metric=success_rate&days=${days}`)
  ]);
  if(!agentData) return;
  
  app.innerHTML = `
    <div class="kb-header">
      <h2>📊 Analytics</h2>
      <div class="kb-filters">
        <select id="analytics-period" onchange="location.hash='#analytics?days='+this.value">
          <option value="7" ${days==='7'?'selected':''}>7 days</option>
          <option value="14" ${days==='14'?'selected':''}>14 days</option>
          <option value="30" ${days==='30'?'selected':''}>30 days</option>
          <option value="90" ${days==='90'?'selected':''}>90 days</option>
        </select>
        <button class="btn btn-s btn-sm" onclick="exportAnalytics()">📥 Export</button>
      </div>
    </div>
    <div style="padding:0 24px 24px">
      ${agentData.agents.length === 0 ? 
        '<div class="empty"><div class="empty-icon">📊</div><h3>No agent data yet</h3><p>Register agents and create tasks to see analytics</p></div>' :
        `<div class="agent-cards">${agentData.agents.map(a => renderAgentCard(a, days)).join('')}</div>`
      }
    </div>`;
}

function renderAgentCard(a, days){
  const kpi = a.kpi || {};
  const sr = kpi.avg_success_rate || 0;
  const srColor = sr >= 80 ? 'var(--ok)' : sr >= 50 ? 'var(--warn)' : 'var(--err)';
  return `<div class="agent-card">
    <div class="agent-card-name">
      <span style="font-size:24px">${esc(a.avatar)}</span>
      <div>
        <div style="font-weight:600;font-size:14px">${esc(a.name)}</div>
        <div style="font-size:12px;color:var(--t2)">${esc(a.role||'')}</div>
      </div>
      <span style="margin-left:auto;font-size:11px;color:var(--t2)">${a.is_active ? '🟢 Active' : '⚪ Inactive'}</span>
    </div>
    <div class="agent-card-bar"><div class="agent-card-bar-fill" style="width:${Math.min(sr,100)}%;background:${srColor}"></div></div>
    <div class="agent-card-stats">
      <div><div class="stat-val">${kpi.total_tasks_created||0}</div><div class="stat-lbl">Created</div></div>
      <div><div class="stat-val">${kpi.total_tasks_completed||0}</div><div class="stat-lbl">Completed</div></div>
      <div><div class="stat-val" style="color:${srColor}">${sr}%</div><div class="stat-lbl">Success Rate</div></div>
      <div><div class="stat-val">${kpi.avg_completion_hours||0}h</div><div class="stat-lbl">Avg Time</div></div>
      <div><div class="stat-val">${kpi.total_activity||0}</div><div class="stat-lbl">Activities</div></div>
    </div>
  </div>`;
}

async function exportAnalytics(){
  const days = document.getElementById('analytics-period')?.value || '7';
  const data = await api('GET', `/api/analytics/export?format=csv&days=${days}`);
  if(!data || !data.content) return toast('No data to export','err');
  const blob = new Blob([data.content], {type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = data.filename || 'agentboard_analytics.csv';
  a.click();
  toast('Exported '+data.rows+' rows');
}


