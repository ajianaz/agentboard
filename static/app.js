// ── State ──
let S={projects:[],currentSlug:null,poll:null,taskPanelOpen:false};

// ── Auth helpers ──
function isAuthenticated(){
  return !!localStorage.getItem('ab_key');
}

// ── API ──
async function api(m,p,b){
  const k=localStorage.getItem('ab_key');
  // GET requests work without auth (public read mode)
  // POST/PATCH/DELETE require auth — prompt setup if no key
  const isWrite=(m==='POST'||m==='PATCH'||m==='DELETE');
  if(isWrite&&!k){
    toast('Authentication required to modify data','err');
    showSetup();
    return null;
  }
  const o={method:m,headers:{'Content-Type':'application/json'}};
  if(k)o.headers['Authorization']='Bearer '+k;
  if(b)o.body=JSON.stringify(b);
  try{
    const r=await fetch(p,o);
    if(r.status===401){
      if(k){
        localStorage.removeItem('ab_key');
        toast('API key invalid — cleared','err');
        updateAuthBadge();
      }
      if(isWrite)showSetup();
      return null;
    }
    if(r.status===503){
      const d=await r.json();
      if(d.code==='MAINTENANCE'){
        toast('System is in maintenance mode — read-only','warn');
        showMaintenanceBanner();
      }
      return null;
    }
    const d=await r.json();
    if(!r.ok){toast(d.error||'Request failed','err');return null}
    return d;
  }catch(e){toast('Network error','err');return null}
}

// ── Toast ──
function toast(msg,type='info'){
  const c=document.getElementById('toast-c');
  const t=document.createElement('div');
  t.className='toast toast-'+type;t.textContent=msg;
  c.appendChild(t);
  setTimeout(()=>t.remove(),3500);
}

// ── Markdown ──
function md(t){
  if(!t)return'';
  let h=t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  h=h.replace(/```(\w*)\n([\s\S]*?)```/g,'<pre><code>$2</code></pre>');
  h=h.replace(/`([^`]+)`/g,'<code>$1</code>');
  h=h.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  h=h.replace(/^## (.+)$/gm,'<h2>$1</h2>');
  h=h.replace(/^# (.+)$/gm,'<h1>$1</h1>');
  h=h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  h=h.replace(/\*(.+?)\*/g,'<em>$1</em>');
  h=h.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2">$1</a>');
  h=h.replace(/^> (.+)$/gm,'<blockquote>$1</blockquote>');
  h=h.replace(/^---$/gm,'<hr>');
  h=h.replace(/^- (.+)$/gm,'<li>$1</li>');
  h=h.replace(/^(\d+)\. (.+)$/gm,'<li>$2</li>');
  h=h.replace(/(<li>.*<\/li>)/s,'<ul>$1</ul>');
  h=h.replace(/<\/ul>\s*<ul>/g,'');
  h=h.replace(/\n\n/g,'</p><p>');
  h=h.replace(/\n/g,'<br>');
  if(!h.startsWith('<'))h='<p>'+h+'</p>';
  return h;
}

// ── Modal ──
function openModal(html){
  document.getElementById('modal').innerHTML=html;
  document.getElementById('modal-bg').classList.add('open');
}
function closeModal(){document.getElementById('modal-bg').classList.remove('open')}

// ── Task Panel ──
function openTaskPanel(task){
  S.taskPanelOpen=true;
  const p=document.getElementById('task-panel');
  const priorities={'critical':'#ef4444','high':'#f97316','medium':'#eab308','low':'#22c55e','none':'#6b7280'};
  const authed=isAuthenticated();
  const taskTypes={milestone:'🏁',feature:'✨',bugfix:'🐛',chore:'🔧',task:'📋',refactor:'🔧',design:'🎨',content:'✍️',copywriting:'📝',review:'👀',campaign:'📣',outreach:'🤝',analytics:'📊',planning:'📋',operations:'⚙️',research:'🔍',meeting:'🤝'};
  let h=`<div class="panel-hdr"><div id="tp-title-text" style="flex:1;font-weight:600;font-size:15px">${esc(task.title)}</div><button class="btn-icon" onclick="closeTaskPanel()">✕</button></div>`;
  h+=`<div class="panel-body">`;
  h+=`<div class="panel-sec"><div class="field-row"><div><label>Type</label><div style="padding:6px 0;font-size:13px;color:var(--t1)">${taskTypes[task.type]||taskTypes.task} ${esc(task.type||'task')}</div></div>`;
  h+=`<div><label>Status</label><div style="padding:6px 0;font-size:13px;color:var(--t1)">${task.status.replace('_',' ')}</div></div></div></div>`;
  h+=`<div class="panel-sec"><div class="field-row"><div><label>Priority</label><div style="padding:6px 0;font-size:13px;color:var(--t1)">${task.priority||'none'}</div></div>`;
  h+=`<div class="panel-sec"><div class="field-row"><div><label>Assignee</label><div style="padding:6px 0;font-size:13px;color:var(--t1)">${esc(task.assignee||'Unassigned')}</div></div>`;
  h+=`<div><label>Due Date</label><div style="padding:6px 0;font-size:13px;color:var(--t1)">${task.due_date||'—'}</div></div></div></div>`;
  h+=`<div class="panel-sec"><label>Tags</label><div style="padding:6px 0;font-size:13px;color:var(--t1)">${esc((task.tags||[]).join(', ')||'—')}</div></div>`;
  h+=`<div class="panel-sec"><label>Description</label><div class="panel-desc-readonly">${md(task.description||'No description')}</div></div>`;
  if(task.status==='proposed'&&authed){
    h+=`<div style="display:flex;gap:8px"><button class="btn btn-ok" onclick="hitlAction('${task.id}','todo','approved')">✓ Approve</button><button class="btn btn-d" onclick="hitlAction('${task.id}','rejected','rejected')">✕ Reject</button></div>`;
  }
  if(task.status==='review'&&authed){
    h+=`<div style="display:flex;gap:8px"><button class="btn btn-ok" onclick="hitlAction('${task.id}','done','approved')">✓ Approve</button><button class="btn btn-warn" onclick="hitlAction('${task.id}','in_progress','changes requested')">↩ Changes</button></div>`;
  }
  if(authed){
    h+=`<button class="btn btn-s btn-sm" style="margin-top:8px" onclick="editTask('${task.id}')">✏️ Edit</button>`;
  }
  h+=`</div>`;
  h+=`<div class="panel-comments"><div class="comment-add">${authed?'<input id="tp-comment" placeholder="Add comment…"><button class="btn btn-p btn-sm" onclick="addComment(\''+task.id+'\')">Send</button>':'<div style="font-size:12px;color:var(--t2);padding:8px 0">🔓 Authenticate to add comments</div>'}</div><div id="tp-comments"></div></div>`;
  p.innerHTML=h;
  document.getElementById('panel-bg').classList.add('open');
  p.classList.add('open');
  loadComments(task.id);
}
function editTask(id){
  // Reload task data then show editable panel
  api('GET','/api/tasks/'+id).then(data=>{
    if(data)openTaskPanelEdit(data.task||data);
  });
}
function openTaskPanelEdit(task){
  S.taskPanelOpen=true;
  const p=document.getElementById('task-panel');
  const priorities={'critical':'#ef4444','high':'#f97316','medium':'#eab308','low':'#22c55e','none':'#6b7280'};
  const statuses=['proposed','todo','in_progress','review','done','rejected'];
  const presetTypes={milestone:'🏁 Milestone',feature:'✨ Feature',task:'📋 Task',bugfix:'🐛 Bugfix',chore:'🔧 Chore',refactor:'🔧 Refactor',design:'🎨 Design',content:'✍️ Content',copywriting:'📝 Copywriting',review:'👀 Review',campaign:'📣 Campaign',outreach:'🤝 Outreach',analytics:'📊 Analytics',planning:'📋 Planning',operations:'⚙️ Operations',research:'🔍 Research',meeting:'🤝 Meeting'};
  const curType=task.type||'task';
  const isPreset=curType in presetTypes;
  let typeOpts=Object.entries(presetTypes).map(([k,v])=>`<option value="${k}" ${curType===k?'selected':''}>${v}</option>`).join('');
  typeOpts+=`<option value="__custom" ${!isPreset?'selected':''}>✏️ Custom...</option>`;
  let h=`<div class="panel-hdr"><input id="tp-title" value="${esc(task.title)}"><button class="btn-icon" onclick="closeTaskPanel()">✕</button></div>`;
  h+=`<div class="panel-body">`;
  h+=`<div class="panel-sec"><div class="field-row"><div><label>Type</label><select id="tp-type" onchange="document.getElementById('tp-custom-type').style.display=this.value==='__custom'?'block':'none'">${typeOpts}</select><input id="tp-custom-type" placeholder="custom-type" value="${isPreset?'':esc(curType)}" style="display:${!isPreset?'block':'none'};margin-top:4px;width:100%;font-size:12px;padding:4px 6px;border:1px solid var(--b1);border-radius:4px;background:var(--bg1);color:var(--t1)"></div>`;
  h+=`<div><label>Status</label><select id="tp-status">${statuses.map(s=>`<option value="${s}" ${task.status===s?'selected':''}>${s.replace('_',' ')}</option>`).join('')}</select></div></div></div>`;
  h+=`<div><label>Priority</label><select id="tp-priority">${Object.entries(priorities).map(([k,v])=>`<option value="${k}" ${task.priority===k?'selected':''}>${k}</option>`).join('')}</select></div></div></div>`;
  h+=`<div class="panel-sec"><div class="field-row"><div><label>Assignee</label><input id="tp-assignee" value="${esc(task.assignee||'')}"></div>`;
  h+=`<div><label>Due Date</label><input id="tp-due" type="date" value="${task.due_date||''}"></div></div></div>`;
  h+=`<div class="panel-sec"><label>Tags</label><input id="tp-tags" value="${esc((task.tags||[]).join(', '))}"></div>`;
  h+=`<div class="panel-sec"><label>Description</label><textarea id="tp-desc" rows="6">${esc(task.description||'')}</textarea></div>`;
  h+=`</div>`;
  h+=`<div class="panel-comments"><div class="comment-add"><input id="tp-comment" placeholder="Add comment…"><button class="btn btn-p btn-sm" onclick="addComment('${task.id}')">Send</button></div><div id="tp-comments"></div></div>`;
  p.innerHTML=h;
  document.getElementById('panel-bg').classList.add('open');
  p.classList.add('open');
  loadComments(task.id);
  p.querySelectorAll('#tp-title,#tp-status,#tp-type,#tp-priority,#tp-assignee,#tp-due,#tp-tags').forEach(el=>{
    el.addEventListener('change',()=>saveTask(task.id));
  });
  document.getElementById('tp-desc').addEventListener('blur',()=>saveTask(task.id));
}
function closeTaskPanel(){
  S.taskPanelOpen=false;
  document.getElementById('task-panel').classList.remove('open');
  document.getElementById('panel-bg').classList.remove('open');
}
async function saveTask(id){
  const body={
    title:document.getElementById('tp-title').value,
    status:document.getElementById('tp-status').value,
    type:document.getElementById('tp-type').value==='__custom'?document.getElementById('tp-custom-type').value.trim():document.getElementById('tp-type').value,
    priority:document.getElementById('tp-priority').value,
    assignee:document.getElementById('tp-assignee').value,
    due_date:document.getElementById('tp-due').value||null,
    tags:document.getElementById('tp-tags').value.split(',').map(t=>t.trim()).filter(Boolean),
    description:document.getElementById('tp-desc').value
  };
  await api('PATCH','/api/tasks/'+id,body);
  setTimeout(()=>render(),300);
}
async function hitlAction(id,status){
  await api('PATCH','/api/tasks/'+id,{status});
  closeTaskPanel();
  toast('Task updated','ok');
  setTimeout(()=>render(),300);
}
async function addComment(taskId){
  const input=document.getElementById('tp-comment');
  const content=input.value.trim();
  if(!content)return;
  await api('POST','/api/tasks/'+taskId+'/comments',{content});
  input.value='';
  loadComments(taskId);
}
async function loadComments(taskId){
  const data=await api('GET','/api/tasks/'+taskId+'/comments');
  const el=document.getElementById('tp-comments');
  if(!el)return;
  if(!data||!data.comments.length){el.innerHTML='';return}
  el.innerHTML=data.comments.map(c=>`<div class="comment"><span class="comment-author">${esc(c.author)}</span><span class="comment-time">${fmtTime(c.created_at)}</span><div class="comment-text">${esc(c.content)}</div></div>`).join('');
  el.scrollTop=el.scrollHeight;
}

// ── Visibility helpers ──
function visBadge(visibility){
  if(visibility==='hidden')return`<span class="vis-badge hid" title="Hidden">🚫</span>`;
  return`<span class="vis-badge pub" title="Public">👁️</span>`;
}
async function toggleProjectVisibility(slug,currentVis){
  const next=currentVis==='hidden'?'public':'hidden';
  const ok=await api('PATCH','/api/projects/'+slug,{visibility:next});
  if(ok){
    toast(`Project visibility set to ${next}`,'ok');
    render();
  }
}
async function toggleDiscussionVisibility(id,currentVis){
  const next=currentVis==='hidden'?'public':'hidden';
  const ok=await api('PATCH','/api/discussions/'+id,{visibility:next});
  if(ok){
    toast(`Discussion visibility set to ${next}`,'ok');
    renderDiscussions(document.getElementById('app'));
  }
}

async function togglePageVisibility(pageId, currentVis, projSlug){
  const next = currentVis==='hidden'?'public':'hidden';
  const ok=await api('PATCH',`/api/pages/${pageId}`,{visibility:next});
  if(ok){
    toast(`Page visibility set to ${next}`,'ok');
    renderDocsHub(document.getElementById('app'), projSlug);
  }
}

// ── Setup ──
function showSetup(){
  document.getElementById('app').innerHTML=`<div class="setup"><div class="setup-card"><h1>Agent<span>Board</span></h1><p>Enter your API key (shown when server starts)</p><input id="s-key" type="password" placeholder="API Key"><button class="btn btn-p" style="width:100%" onclick="doSetup()">Connect</button><div class="err" id="s-err"></div></div></div>`;
  const inp=document.getElementById('s-key');
  if(inp)inp.addEventListener('keydown',e=>{if(e.key==='Enter')doSetup()});
}
async function validateKey(key){
  try{
    const r=await fetch('/api/agents',{headers:{'Authorization':'Bearer '+key}});
    return r.ok;
  }catch(e){return false}
}
async function doSetup(){
  const key=document.getElementById('s-key').value.trim();
  if(!key){document.getElementById('s-err').textContent='API key required';return}
  document.getElementById('s-err').textContent='Verifying…';
  const ok=await validateKey(key);
  if(!ok){document.getElementById('s-err').textContent='Invalid API key';localStorage.removeItem('ab_key');return}
  localStorage.setItem('ab_key',key);
  toast('Connected!','ok');
  updateAuthBadge();
  render();
}
async function sidebarAuth(){
  const inp=document.getElementById('sb-key-input');
  const key=inp?inp.value.trim():'';
  if(!key){toast('Enter an API key','warn');return}
  inp.disabled=true;inp.placeholder='Verifying…';
  const ok=await validateKey(key);
  inp.disabled=false;inp.placeholder='API Key…';
  if(!ok){toast('Invalid API key','err');localStorage.removeItem('ab_key');updateAuthBadge();return}
  localStorage.setItem('ab_key',key);
  toast('Authenticated ✓','ok');
  updateAuthBadge();
}
function sidebarLogout(){
  localStorage.removeItem('ab_key');
  toast('Key removed','ok');
  updateAuthBadge();
}
function updateAuthBadge(){
  const icon=document.getElementById('sb-auth-icon');
  const inp=document.getElementById('sb-key-input');
  const btn=document.getElementById('sb-key-btn');
  const out=document.getElementById('sb-key-logout');
  const authed=isAuthenticated();
  // Toggle visibility of auth-gated sidebar links (exclude WIP-hidden: analytics, agents)
  ['sb-activity','sb-settings'].forEach(id=>{
    const el=document.getElementById(id);
    if(el)el.style.display=authed?'':'none';
  });
  if(!icon)return;
  if(authed){
    icon.textContent='🔒';
    icon.title='Authenticated — click to change key';
    if(inp){inp.style.display='none';inp.value=''}
    if(btn)btn.style.display='none';
    if(out)out.style.display='';
  }else{
    icon.textContent='🔓';
    icon.title='No API key — read-only mode';
    if(inp)inp.style.display='';
    if(btn)btn.style.display='';
    if(out)out.style.display='none';
  }
}
// ── Maintenance banner ──
function showMaintenanceBanner(){
  let el=document.getElementById('maintenance-banner');
  if(el)return;
  el=document.createElement('div');
  el.id='maintenance-banner';
  el.style.cssText='position:fixed;top:0;left:0;right:0;z-index:9999;background:var(--err);color:#fff;text-align:center;padding:8px 16px;font-size:13px;font-weight:600;display:flex;align-items:center;justify-content:center;gap:8px';
  el.innerHTML='<span>⚠️ Maintenance Mode — System is read-only</span><button onclick="this.parentElement.remove()" style="background:none;border:none;cursor:pointer;font-size:16px;color:#fff">✕</button>';
  document.body.prepend(el);
  document.body.style.paddingTop='36px';
  const sb=document.getElementById('sidebar');
  if(sb)sb.style.top='36px';
  // Store cleanup function on element
  el._cleanup=function(){
    document.body.style.paddingTop='';
    const s=document.getElementById('sidebar');
    if(s)s.style.top='';
  };
  const origRemove=el.remove.bind(el);
  el.remove=function(){if(el._cleanup)el._cleanup();origRemove();};
}

async function checkHealth(){
  try{
    const r=await fetch('/api/health');
    if(!r.ok)return;
    const d=await r.json();
    if(d.version){
      const el=document.getElementById('sb-ver');
      if(el)el.textContent='v'+d.version;
    }
    if(d.maintenance)showMaintenanceBanner();
    else{
      const el=document.getElementById('maintenance-banner');
      if(el)el.remove();
    }
  }catch(e){}
}

// ── Sidebar ──
async function loadSidebar(){
  updateAuthBadge();
  const data=await api('GET','/api/projects');
  if(!data)return;
  S.projects=data.projects||[];
  const el=document.getElementById('sb-projects');
  el.innerHTML=S.projects.map(p=>{
    return`<a href="#project/${p.slug}/board"><span class="sb-proj-icon">${p.icon||'📋'}</span>${esc(p.name)}${isAuthenticated()?visBadge(p.visibility):''}<span class="sb-count">${p.task_count||0}</span></a>`;
  }).join('');
  const addProj=document.getElementById('sb-add-proj');
  addProj.innerHTML=isAuthenticated()?'<a href="#" class="sb-add" id="add-proj-btn">+ New Project</a>':'';
  addProj.querySelector('#add-proj-btn')?.addEventListener('click',e=>{
    e.preventDefault();
    openModal(`<h3>New Project</h3>
    <div class="form-group"><label>Name</label><input id="np-name" placeholder="Project name"></div>
    <div class="form-group"><label>Description</label><textarea id="np-desc" rows="2" placeholder="What is this project about?"></textarea></div>
    <div class="form-group"><div class="field-row"><div><label>Icon</label><input class="icon-inp" id="np-icon" value="📋"></div><div><label>Color</label><input class="color-inp" id="np-color" type="color" value="#3b82f6"></div></div></div>
    <div style="display:flex;gap:8px;justify-content:flex-end"><button class="btn btn-s" onclick="closeModal()">Cancel</button><button class="btn btn-p" onclick="createProject()">Create</button></div>`);
  });
  highlightSidebarLink();
}

function highlightSidebarLink(){
  const hash=location.hash||'#overview';
  document.querySelectorAll('#sidebar a').forEach(a=>{
    a.classList.remove('active');
    const href=a.getAttribute('href')||'';
    if(href&&hash===href){a.classList.add('active')}
    // Match project sub-routes (board/docs/settings)
    if(href.startsWith('#project/')&&hash.startsWith(href.replace(/\/board$/,''))){a.classList.add('active')}
    // Match #docs and #docs/{slug}
    if(href==='#docs'&&hash.startsWith('#docs')){a.classList.add('active')}
  });
}

// ── Router ──
function getRoute(){
  const h=location.hash||'#overview';
  if(h==='#overview')return{view:'overview'};
  if(h.startsWith('#docs/')){const s=h.split('/')[1];return{view:'docs',slug:s}}
  if(h==='#docs')return{view:'docs'};
  if(h==='#analytics')return{view:'analytics'};
  if(h==='#discussions')return{view:'discussions'};
  if(h==='#activity')return{view:'activity'};
  if(h==='#agents')return{view:'agents'};
  if(h==='#inbox')return{view:'inbox'};
  const m=h.match(/^#project\/([^/]+)\/(.+)$/);
  if(m)return{view:m[2],slug:m[1]};
  return{view:'overview'};
}

async function render(){
  const{view,slug}=getRoute();
  await loadSidebar();
  const app=document.getElementById('app');
  // Close panel on nav
  closeTaskPanel();
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('open');
  switch(view){
    case'overview':if(!isAuthenticated()){await renderPublicDashboard(app)}else{await renderOverview(app)};break;
    case'board':await renderBoard(app,slug);break;
    case'tree':await renderTree(app,slug);break;
    case'docs':await renderDocsHub(app,slug);break;
    case'settings':if(slug)await renderProjectSettings(app,slug);else await renderSystemSettings(app);break;
    case'agents':await renderAgents(app);break;
    case'analytics':await renderAnalytics(app);break;
    case'discussions':await renderDiscussions(app);break;
    case'activity':await renderActivity(app);break;
    case'inbox':await renderInbox(app);break;
    default:app.innerHTML=`<div class="empty"><div class="empty-icon">🔍</div><h3>Not found</h3><p>This view doesn't exist</p></div>`;
  }
}

// ── Overview ──
async function renderOverview(app){
  const[stats,projData,tasksData]=await Promise.all([
    api('GET','/api/stats'),
    api('GET','/api/projects'),
    api('GET','/api/tasks?project=all')
  ]);
  if(!stats){app.innerHTML='';return}
  const tasks=tasksData?.tasks||[];
  const projects=projData?.projects||[];
  // Stats bar
  let h=`<div class="stats-bar">`;
  const todoCount = (stats.todo_tasks||0)+(stats.proposed_tasks||0);
  h+=statCard(stats.total_tasks||0,'Total Tasks','var(--ac)');
  h+=statCard(todoCount,'Todo','var(--warn)');
  h+=statCard(stats.in_progress_tasks||0,'In Progress','var(--ac)');
  h+=statCard(stats.review_tasks||0,'In Review','var(--rev)');
  h+=statCard(stats.done_tasks||0,'Done','var(--ok)');
  h+=`</div>`;
  // Project grid
  h+=`<div style="padding:24px 24px 8px"><h2 style="font-size:16px;font-weight:600">Projects</h2></div>`;
  h+=`<div class="proj-grid">`;
  projects.forEach(p=>{
    const total=stats.per_project?.[p.slug]?.total||0;
    const done=stats.per_project?.[p.slug]?.done||0;
    const pct=total?Math.round(done/total*100):0;
    h+=`<div class="proj-card" onclick="location.hash='#project/${p.slug}/board'">
      <div class="proj-card-hdr"><span class="proj-card-icon">${p.icon||'📋'}</span><span class="proj-card-name">${esc(p.name)}</span>${isAuthenticated()?visBadge(p.visibility):''}</div>
      <div class="proj-card-bar"><div class="proj-card-bar-fill" style="width:${pct}%"></div></div>
      <div class="proj-card-meta"><span>${done}/${total} tasks</span><span>${pct}%</span></div>
    </div>`;
  });
  if(!projects.length)h+=`<div class="empty"><div class="empty-icon">📋</div><h3>No projects yet</h3><p>Create your first project to get started</p></div>`;
  h+=`</div>`;
  // Attention queue
  const attn=tasks.filter(t=>t.status==='proposed'||t.status==='review');
  if(attn.length){
    h+=`<div class="attn-section"><div class="attn-title">⚠️ Needs Attention (${attn.length})</div>`;
    attn.forEach(t=>{
      const color=t.status==='proposed'?'var(--warn)':'var(--rev)';
      const label=t.status==='proposed'?'Awaiting approval':'In review';
      h+=`<div class="attn-item" onclick="loadAndOpenTask('${t.id}')">
        <div class="attn-dot" style="background:${color}"></div>
        <div class="attn-info"><div class="title">${esc(t.title)}</div><div class="sub">${esc(t.project_name||'')} · ${label}</div></div>
        <div class="attn-actions">
          ${isAuthenticated()&&t.status==='proposed'?`<button class="btn btn-ok btn-sm" onclick="event.stopPropagation();quickHitl('${t.id}','todo')">✓</button>`:''}
          ${isAuthenticated()&&t.status==='review'?`<button class="btn btn-ok btn-sm" onclick="event.stopPropagation();quickHitl('${t.id}','done')">✓</button>`:''}
        </div>
      </div>`;
    });
    h+=`</div>`;
  }
  app.innerHTML=h;
}

function statCard(val,label,color){
  return`<div class="stat-card"><div class="stat-val" style="color:${color}">${val}</div><div class="stat-lbl">${label}</div></div>`;
}

async function loadAndOpenTask(id){
  const data=await api('GET','/api/tasks/'+id);
  if(data)openTaskPanel(data.task||data);
}
async function quickHitl(id,status){
  await api('PATCH','/api/tasks/'+id,{status});
  toast('Task updated','ok');
  setTimeout(()=>render(),300);
}

// ── Inbox ──
async function renderInbox(app){
  const data=await api('GET','/api/messages?agent='+(S.agentName||''));
  if(!data){app.innerHTML='<div class="empty"><h3>Could not load messages</h3></div>';return}
  const msgs=data.messages||[];
  const unread=data.unread_count||0;
  let h=`<div class="kb-header"><h2>💬 Inbox</h2>
    <div class="kb-filters">
      <select id="inbox-filter" onchange="renderInbox(document.getElementById('app'))">
        <option value="unread"${unread>0?' selected':''}>Unread (${unread})</option>
        <option value="all">All messages</option>
      </select>
      ${isAuthenticated()?`<button class="btn btn-s btn-sm" onclick="markAllRead()">✓ Mark all read</button>`:''}
    </div></div>`;
  if(msgs.length===0){
    h+=`<div class="empty"><div class="empty-icon">📭</div><h3>No messages</h3><p>Your inbox is empty</p></div>`;
  } else {
    msgs.forEach(m=>{
      const unreadCls=m.is_read?'':' unread';
      const timeAgo=new Date(m.created_at).toLocaleString();
      h+=`<div class="msg-item${unreadCls}" onclick="openMessage('${m.id}')">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span class="msg-subject">${esc(m.subject||'No subject')}</span>
          <span style="font-size:11px;color:var(--t2)">${timeAgo}</span>
        </div>
        <div class="msg-from">From: ${esc(m.from_agent)}${m.to_agent?' → '+esc(m.to_agent):' (broadcast)'}</div>
        <div class="msg-content">${esc(m.content)}</div>
      </div>`;
    });
  }
  app.innerHTML=h;
}
async function markAllRead(){
  await api('PATCH','/api/messages/read-all');
  toast('All marked as read','ok');
  setTimeout(()=>renderInbox(document.getElementById('app')),200);
  updateInboxBadge(0);
}
async function openMessage(id){
  await api('PATCH','/api/messages/'+id+'/read');
  const data=await api('GET','/api/messages?agent='+(S.agentName||''));
  if(data)updateInboxBadge(data.unread_count||0);
  renderInbox(document.getElementById('app'));
}
function updateInboxBadge(count){
  const b=document.getElementById('sb-inbox-badge');
  if(!b)return;
  if(count>0){b.style.display='inline';b.textContent=count>99?'99+':count}
  else{b.style.display='none'}
}
async function pollInboxBadge(){
  if(!isAuthenticated())return;
  const data=await api('GET','/api/messages?agent='+(S.agentName||''));
  if(data)updateInboxBadge(data.unread_count||0);
}

// ── Kanban Board ──
async function renderBoard(app,slug){
  const typeFilter=document.getElementById('kb-filter-type')?.value||'';
  const priFilter=document.getElementById('kb-filter-priority')?.value||'';
  const assignFilter=document.getElementById('kb-filter-assignee')?.value||'';
  let taskUrl='/api/projects/'+slug+'/tasks';
  const qp=[];
  if(typeFilter)qp.push('type='+typeFilter);
  if(priFilter)qp.push('priority='+priFilter);
  if(assignFilter)qp.push('assignee='+assignFilter);
  if(qp.length)taskUrl+='?'+qp.join('&');
  const[proj,tasksData]=await Promise.all([
    api('GET','/api/projects/'+slug),
    api('GET',taskUrl)
  ]);
  if(!proj){app.innerHTML='<div class="empty"><h3>Project not found</h3></div>';return}
  const project=proj.project||proj;
  const tasks=tasksData?.tasks||[];
  const statuses=project.statuses||[
    {key:'proposed',label:'Proposed',color:'#f59e0b'},
    {key:'todo',label:'To Do',color:'#6b7280'},
    {key:'in_progress',label:'In Progress',color:'#3b82f6'},
    {key:'review',label:'Review',color:'#8b5cf6'},
    {key:'done',label:'Done',color:'#22c55e'}
  ];
  const priorities={'critical':'#ef4444','high':'#f97316','medium':'#eab308','low':'#22c55e','none':'#6b7280'};
  const taskTypes={milestone:'🏁',feature:'✨',bugfix:'🐛',chore:'🔧',task:'📋',refactor:'🔧',design:'🎨',content:'✍️',copywriting:'📝',review:'👀',campaign:'📣',outreach:'🤝',analytics:'📊',planning:'📋',operations:'⚙️',research:'🔍',meeting:'🤝'};
  // Dynamic type filter: presets + any custom types from existing tasks
  const usedTypes=new Set(tasks.map(t=>t.type||'task'));
  const allFilterTypes=[...new Set([...Object.keys(taskTypes),...usedTypes])].sort();
  let h=`<div class="kb-header">
    <h2>${project.icon||'📋'} ${esc(project.name)}</h2>
    <div class="kb-filters">
      <select id="kb-filter-assignee" onchange="render()"><option value="">All assignees</option></select>
      <select id="kb-filter-priority" onchange="render()"><option value="">All priorities</option>${Object.keys(priorities).map(k=>`<option value="${k}" ${priFilter===k?'selected':''}>${k}</option>`).join('')}</select>
      <select id="kb-filter-type" onchange="render()"><option value="" ${typeFilter===''?'selected':''}>All types</option>${allFilterTypes.map(k=>`<option value="${k}" ${typeFilter===k?'selected':''}>${taskTypes[k]||'🏷️'} ${k}</option>`).join('')}</select>
      ${isAuthenticated()?`<button class="btn btn-p btn-sm" onclick="showNewTask('${slug}')">+ New Task</button>`:''}
    </div>
    <a href="#project/${slug}/docs" class="btn btn-s btn-sm">📄 Docs</a>
    <div class="view-toggle">
      <button class="${true?'active':''}" onclick="location.hash='#project/${slug}/board'">📋 Board</button>
      <button onclick="location.hash='#project/${slug}/tree'">🌳 Tree</button>
    </div>
    ${isAuthenticated()?`<a href="#project/${slug}/settings" class="btn btn-s btn-sm">⚙️ Settings</a>`:''}
  </div>`;
  h+=`<div class="kb-board">`;
  statuses.forEach(s=>{
    const colTasks=tasks.filter(t=>t.status===s.key);
    h+=`<div class="kb-col">
      <div class="kb-col-hdr"><div class="kb-col-dot" style="background:${s.color}"></div>${esc(s.label)}<span class="kb-col-count">${colTasks.length}</span></div>
      <div class="kb-col-body" data-status="${s.key}" ondragover="onDragOver(event)" ondrop="onDrop(event,'${s.key}','${slug}')" ondragleave="onDragLeave(event)">`;
    colTasks.forEach(t=>{
      const cardClass=t.status==='proposed'?'kb-card-proposed':t.status==='review'?'kb-card-review':'';
      const tt=t.type||'task';
      h+=`<div class="kb-card ${cardClass}" draggable="true" data-id="${t.id}" ondragstart="onDragStart(event)" onclick="loadAndOpenTask('${t.id}')">
        <div class="kb-card-title">${esc(t.title)}</div>
        <div class="kb-card-meta">
          <div class="kb-card-priority" style="background:${priorities[t.priority]||priorities.none}"></div>
          <span class="type-badge type-${tt}">${taskTypes[tt]||'📋'}</span>
          ${t.assignee?`<span class="kb-card-assignee">${esc(t.assignee)}</span>`:''}
          ${t.due_date?`<span class="kb-card-due">📅 ${t.due_date.slice(5)}</span>`:''}
        </div>
      </div>`;
    });
    h+=`</div></div>`;
  });
  h+=`</div>`;
  app.innerHTML=h;
  // Restore filter selections after DOM re-render
  const af=document.getElementById('kb-filter-assignee');
  if(af)af.value=assignFilter;
}

// ── Tree View ──
async function renderTree(app,slug){
  const typeFilter=new URLSearchParams(location.hash.split('?')[1]||'').get('type')||'';
  const priFilter=new URLSearchParams(location.hash.split('?')[1]||'').get('priority')||'';
  let taskUrl='/api/projects/'+slug+'/tasks';
  const qp=[];
  if(typeFilter)qp.push('type='+typeFilter);
  if(priFilter)qp.push('priority='+priFilter);
  if(qp.length)taskUrl+='?'+qp.join('&');
  const[proj,tasksData]=await Promise.all([
    api('GET','/api/projects/'+slug),
    api('GET',taskUrl)
  ]);
  if(!proj){app.innerHTML='<div class="empty"><h3>Project not found</h3></div>';return}
  const project=proj.project||proj;
  const tasks=tasksData?.tasks||[];
  const priorities={'critical':'#ef4444','high':'#f97316','medium':'#eab308','low':'#22c55e','none':'#6b7280'};
  const statusColors={'proposed':'#f59e0b','todo':'#6b7280','in_progress':'#3b82f6','review':'#8b5cf6','done':'#22c55e'};
  const taskTypes={milestone:'🏁',feature:'✨',bugfix:'🐛',chore:'🔧',task:'📋',refactor:'🔧',design:'🎨',content:'✍️',copywriting:'📝',review:'👀',campaign:'📣',outreach:'🤝',analytics:'📊',planning:'📋',operations:'⚙️',research:'🔍',meeting:'🤝'};
  const usedTypes=new Set(tasks.map(t=>t.type||'task'));
  const allFilterTypes=[...new Set([...Object.keys(taskTypes),...usedTypes])].sort();

  // Build filter params helper
  function filterParams(extra=''){const p=new URLSearchParams();if(typeFilter)p.set('type',typeFilter);if(priFilter)p.set('priority',priFilter);const s=p.toString();return s?(s+(extra?'&'+extra:'')):(extra||'')}

  let h=`<div class="kb-header">
    <h2>${project.icon||'📋'} ${esc(project.name)}</h2>
    <div class="kb-filters">
      <select id="kb-filter-type" onchange="location.hash='#project/${slug}/tree?'+filterParams('type='+this.value)"><option value="">All types</option>${allFilterTypes.map(k=>`<option value="${k}" ${typeFilter===k?'selected':''}>${taskTypes[k]||'🏷️'} ${k}</option>`).join('')}</select>
      <select id="kb-filter-priority" onchange="location.hash='#project/${slug}/tree?'+filterParams('priority='+this.value)"><option value="">All priorities</option>${Object.keys(priorities).map(k=>`<option value="${k}" ${priFilter===k?'selected':''}>${k}</option>`).join('')}</select>
      ${isAuthenticated()?`<button class="btn btn-p btn-sm" onclick="showNewTask('${slug}')">+ New Task</button>`:''}
    </div>
    <a href="#project/${slug}/docs" class="btn btn-s btn-sm">📄 Docs</a>
    <div class="view-toggle">
      <button onclick="location.hash='#project/${slug}/board'">📋 Board</button>
      <button class="${true?'active':''}" onclick="location.hash='#project/${slug}/tree'">🌳 Tree</button>
    </div>
    ${isAuthenticated()?`<a href="#project/${slug}/settings" class="btn btn-s btn-sm">⚙️ Settings</a>`:''}
  </div>`;

  // Build tree structure from flat tasks
  const taskMap={};
  tasks.forEach(t=>{taskMap[t.id]=t; t._children=[]});
  const roots=[];
  tasks.forEach(t=>{
    if(t.parent_id&&taskMap[t.parent_id]){taskMap[t.parent_id]._children.push(t)}
    else{roots.push(t)}
  });
  // Sort: by priority weight desc, then by title
  const priWeight={critical:4,high:3,medium:2,low:1,none:0};
  function sortTasks(arr){arr.sort((a,b)=>{(priWeight[b.priority]||0)-(priWeight[a.priority]||0)||a.title.localeCompare(b.title)});arr.forEach(t=>sortTasks(t._children))}
  sortTasks(roots);

  // Track expanded state in sessionStorage
  const expanded=new Set(JSON.parse(sessionStorage.getItem('tree_expanded_'+slug)||'[]'));

  function treeHtml(nodes,depth=0){
    let r='';
    nodes.forEach(t=>{
      const hasKids=t._children.length>0;
      const isExp=expanded.has(t.id);
      const pri=priorities[t.priority]||priorities.none;
      const sc=statusColors[t.status]||statusColors.todo;
      const tt=t.type||'task';
      r+=`<div class="tree-row" data-id="${t.id}" onclick="loadAndOpenTask('${t.id}')">
        <div class="tr-toggle" onclick="event.stopPropagation();toggleTreeNode('${slug}','${t.id}')">${hasKids?(isExp?'▾':'▸'):''}</div>
        <div style="width:${depth*20}px;flex-shrink:0"></div>
        <div style="width:4px;height:16px;border-radius:2px;background:${sc};flex-shrink:0"></div>
        <span class="tr-title">${esc(t.title)}</span>
        <span class="tr-type"><span class="type-badge type-${tt}">${taskTypes[tt]||'📋'}</span></span>
        <span class="tr-pri"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${pri}"></span></span>
        ${t.assignee?`<span class="tr-assignee">${esc(t.assignee)}</span>`:'<span class="tr-assignee"></span>'}
        ${t.due_date?`<span class="tr-due">📅 ${t.due_date.slice(5)}</span>`:'<span class="tr-due"></span>'}
      </div>`;
      if(hasKids&&isExp){
        r+=`<div class="tree-children">${treeHtml(t._children,depth+1)}</div>`;
      }
    });
    return r;
  }

  h+=`<div class="tree-view">
    <div class="tree-header">
      <span></span><span>Title</span><span class="th-type">Type</span><span class="th-pri">Pri</span><span class="th-assignee">Assignee</span><span class="th-due">Due</span>
    </div>`;
  if(roots.length===0){
    h+=`<div class="tree-empty">No tasks yet. Click <strong>+ New Task</strong> to get started.</div>`;
  } else {
    h+=treeHtml(roots);
  }
  h+=`</div>`;
  app.innerHTML=h;
}

// Toggle tree node expansion
function toggleTreeNode(slug,id){
  const key='tree_expanded_'+slug;
  const arr=JSON.parse(sessionStorage.getItem(key)||'[]');
  const idx=arr.indexOf(id);
  if(idx>=0)arr.splice(idx,1);else arr.push(id);
  sessionStorage.setItem(key,JSON.stringify(arr));
  render();
}

// Drag and drop
let dragId=null;
function onDragStart(e){if(!isAuthenticated())return;dragId=e.target.dataset.id;e.target.classList.add('dragging');e.dataTransfer.effectAllowed='move'}
function onDragOver(e){e.preventDefault();e.currentTarget.classList.add('drag-over')}
function onDragLeave(e){e.currentTarget.classList.remove('drag-over')}
async function onDrop(e,status,slug){
  e.preventDefault();e.currentTarget.classList.remove('drag-over');
  if(!dragId)return;
  await api('PATCH','/api/tasks/'+dragId,{status});
  dragId=null;
  toast('Task moved','ok');
  setTimeout(()=>render(),200);
}

function showNewTask(slug){
  openModal(`<h3>New Task</h3>
    <div class="form-group"><label>Title</label><input id="nt-title" placeholder="Task title"></div>
    <div class="form-group"><label>Description</label><textarea id="nt-desc" rows="3"></textarea></div>
    <div class="form-group"><div class="field-row"><div><label>Type</label><select id="nt-type" onchange="document.getElementById('nt-custom-type').style.display=this.value==='__custom'?'block':'none'"><option value="task">📋 Task</option><option value="feature">✨ Feature</option><option value="bugfix">🐛 Bugfix</option><option value="chore">🔧 Chore</option><option value="milestone">🏁 Milestone</option><option value="design">🎨 Design</option><option value="content">✍️ Content</option><option value="research">🔍 Research</option><option value="campaign">📣 Campaign</option><option value="analytics">📊 Analytics</option><option value="meeting">🤝 Meeting</option><option value="__custom">✏️ Custom…</option></select><input id="nt-custom-type" placeholder="custom-type" style="display:none;margin-top:4px;width:100%;font-size:12px;padding:4px 6px;border:1px solid var(--b1);border-radius:4px;background:var(--bg1);color:var(--t1)"></div><div><label>Priority</label><select id="nt-pri"><option value="none">None</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></div><div><label>Status</label><select id="nt-status"><option value="proposed">Proposed</option><option value="todo">To Do</option></select></div></div></div>
    <div class="form-group"><label>Assignee</label><input id="nt-assignee" placeholder="Agent name"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end"><button class="btn btn-s" onclick="closeModal()">Cancel</button><button class="btn btn-p" onclick="createTask('${slug}')">Create</button></div>`);
}
async function createTask(slug){
  const title=document.getElementById('nt-title').value.trim();
  if(!title){toast('Title required','err');return}
  const body={
    title,
    description:document.getElementById('nt-desc').value,
    type:document.getElementById('nt-type').value==='__custom'?document.getElementById('nt-custom-type').value.trim():document.getElementById('nt-type').value,
    priority:document.getElementById('nt-pri').value,
    status:document.getElementById('nt-status').value,
    assignee:document.getElementById('nt-assignee').value.trim()
  };
  await api('POST','/api/projects/'+slug+'/tasks',body);
  closeModal();
  toast('Task created','ok');
  setTimeout(()=>render(),200);
}

// ── Docs Hub (standalone, cross-project, read-only) ──
// Two modes:
//   1. #docs          — all projects sidebar, read-only viewer
//   2. #docs/{slug}   — filtered to one project, read-only viewer
async function renderDocsHub(app, slug){
  const data = await api('GET', '/api/pages');
  if(!data) {app.innerHTML='';return}
  const groups = data.projects || [];
  const totalCount = groups.reduce((s,g)=>s+g.pages.length,0);

  // Resolve slug: URL → or first project with pages
  if(slug){
    const exists = groups.find(g => g.project.slug === slug);
    if(!exists) slug = null; // project archived or removed, reset
  }
  if(!slug && groups.length > 0) slug = groups[0].project.slug;

  let h = `<div class="docs-layout" style="height:100vh">
    <div class="docs-tree">
      <div class="docs-tree-hdr"><h3>📄 All Docs</h3>
        ${isAuthenticated()?`<button class="btn btn-p btn-sm" onclick="addStandalonePage()">+ Standalone</button>`:''}
        <span style="font-size:11px;color:var(--t2)">${totalCount} pages</span>
      </div>`;

  // Cache all pages for tree item clicks (avoids re-fetching)
  _roCachedPages = groups.flatMap(g => g.pages);

  groups.forEach(g => {
    const p = g.project;
    const roots = g.pages.filter(pg => !pg.parent_id);
    const childrenOf = {};
    g.pages.filter(pg => pg.parent_id).forEach(pg => {
      if(!childrenOf[pg.parent_id]) childrenOf[pg.parent_id] = [];
      childrenOf[pg.parent_id].push(pg);
    });
    const isActive = slug === p.slug;
    h += `<div class="docs-proj-group">
      <div class="docs-proj-hdr" onclick="location.hash='#docs/${p.slug}'" style="cursor:pointer;padding:8px 12px;font-weight:600;font-size:13px;display:flex;align-items:center;gap:6px;${isActive?'color:var(--ac)':''}">
        <span>${p.icon||'📋'}</span>${esc(p.name)}<span style="font-size:11px;color:var(--t2)">${roots.length}</span>
      </div>`;
    if(isActive){
      const projSlug = p.slug; // project slug captured in outer scope
      const _treeHtml = (nodes, d) => nodes.map(pg => {
        const kids = childrenOf[pg.id] || [];
        const hasKids = kids.length > 0;
        const exp = d < 1 ? '▾' : (hasKids ? '▸' : '');
        return `<div class="tree-item" data-id="${pg.id}" style="padding-left:${8+d*16}px" onclick="loadPageReadonly('${pg.id}','${projSlug}',_roCachedPages)">
          <span class="toggle">${exp}</span><span class="page-icon">📄</span><span class="page-title">${esc(pg.title)}</span>
          ${isAuthenticated()?`<span class="page-acts">${projSlug==='__standalone__'?visBadge(pg.visibility):''}<button class="btn-icon" style="font-size:12px" onclick="event.stopPropagation();deletePage('${pg.id}','${projSlug}')">🗑</button>${projSlug==='__standalone__'?`<button class="btn-icon" style="font-size:12px" title="Toggle visibility" onclick="event.stopPropagation();togglePageVisibility('${pg.id}','${pg.visibility||'public'}')">${pg.visibility==='hidden'?'👁️':'🔒'}</button>`:''}</span>`:''}
        </div>`;
      }).join('');
      h += _treeHtml(roots, 0);
    }
    h += `</div>`;
  });

  if(!groups.length){
    h += `<div class="empty" style="padding:24px"><div class="empty-icon">📄</div><h3>No docs yet</h3><p>Create pages from any project to see them here</p></div>`;
  }
  h += `</div>`;
  h += `<div class="docs-editor" id="docs-editor">
    <div class="docs-editor-hdr">
      <input id="de-title" value="" disabled style="opacity:.7">
      <span style="font-size:11px;color:var(--t2)">📖 Read-only</span>
    </div>
    <div class="docs-editor-body">
      <div class="docs-preview" id="de-preview" style="flex:1"></div>
    </div>
  </div></div>`;
  app.innerHTML = h;

  if(slug){
    const group = groups.find(g => g.project.slug === slug);
    if(group && group.pages.length){
      loadPageReadonly(group.pages[0].id, slug, group.pages);
    }
  }
}

let _roCurrentPageId = null;
let _roCachedPages = null;
async function loadPageReadonly(id, slug, cachedPages){
  _roCurrentPageId = id;
  // Use cached pages from hub if available, otherwise fetch
  let page = null;
  if(cachedPages){
    page = cachedPages.find(p => p.id === id);
  }
  if(!page && slug && slug !== '__standalone__'){
    const data = await api('GET', '/api/projects/'+slug+'/pages');
    if(!data) return;
    page = (data.pages||[]).find(p => p.id === id);
  }
  if(!page) return;
  document.getElementById('de-title').value = page.title || '';
  document.getElementById('de-preview').innerHTML = md(page.content || '');
  document.querySelectorAll('.tree-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === id);
  });
}

// ── Documents (project-scoped, editable) ──
async function renderDocs(app,slug){
  const[proj,pagesData]=await Promise.all([
    api('GET','/api/projects/'+slug),
    api('GET','/api/projects/'+slug+'/pages')
  ]);
  if(!proj){app.innerHTML='<div class="empty"><h3>Project not found</h3></div>';return}
  const project=proj.project||proj;
  const pages=pagesData?.pages||[];
  // Build tree
  const roots=pages.filter(p=>!p.parent_id);
  const childrenOf={};
  pages.filter(p=>p.parent_id).forEach(p=>{
    if(!childrenOf[p.parent_id])childrenOf[p.parent_id]=[];
    childrenOf[p.parent_id].push(p);
  });
  function treeHtml(nodes,depth=0){
    return nodes.map(p=>{
      const kids=childrenOf[p.id]||[];
      const hasKids=kids.length>0;
      const expanded=depth<1?'open':'';
      let h=`<div class="tree-item" data-id="${p.id}" style="padding-left:${8+depth*16}px" onclick="loadPage('${p.id}','${slug}')">
        <span class="toggle">${hasKids?(expanded?'▾':'▸'):''}</span>
        <span class="page-icon">📄</span>
        <span class="page-title">${esc(p.title)}</span>
        <span class="page-acts">
          ${isAuthenticated()?`<button class="btn-icon" style="font-size:12px" onclick="event.stopPropagation();addChildPage('${p.id}','${slug}')">+</button>
          <button class="btn-icon" style="font-size:12px" onclick="event.stopPropagation();deletePage('${p.id}','${slug}')">🗑</button>`:''}
        </span>
      </div>`;
      if(hasKids&&expanded)h+=treeHtml(kids,depth+1);
      return h;
    }).join('');
  }
  const treeHtmlStr=treeHtml(roots);
  let h=`<div class="docs-layout">
    <div class="docs-tree">
      <div class="docs-tree-hdr"><h3>${project.icon||'📋'} ${esc(project.name)}</h3>
        ${isAuthenticated()?`<button class="btn btn-p btn-sm" onclick="addRootPage('${slug}')">+ Page</button>`:''}
      </div>
      ${treeHtmlStr||'<div class="empty" style="padding:24px"><div class="empty-icon">📄</div><h3>No pages</h3></div>'}
    </div>
    <div class="docs-editor" id="docs-editor">
      <div class="docs-editor-hdr">
        <input id="de-title" placeholder="Page title" ${isAuthenticated()?'onblur="savePage()"':'disabled style="opacity:.6"'}>
        ${isAuthenticated()?'<button class="btn btn-s btn-sm" onclick="savePage()">Save</button>':''}
      </div>
      <div class="docs-editor-body">
        <div class="docs-md"><textarea id="de-content" placeholder="Write markdown…" ${isAuthenticated()?'oninput="updatePreview()"':'disabled style="opacity:.6"'}></textarea></div>
        <div class="docs-preview" id="de-preview"></div>
      </div>
    </div>
  </div>`;
  app.innerHTML=h;
  // Load first page if exists
  if(pages.length)loadPage(pages[0].id,slug);
}

let currentPageId=null;
let saveTimer=null;
async function loadPage(id,slug){
  currentPageId=id;
  const data=await api('GET','/api/projects/'+slug+'/pages');
  if(!data)return;
  const pages=data.pages||[];
  const page=pages.find(p=>p.id===id);
  if(!page)return;
  document.getElementById('de-title').value=page.title||'';
  document.getElementById('de-content').value=page.content||'';
  updatePreview();
  // Highlight active
  document.querySelectorAll('.tree-item').forEach(el=>{
    el.classList.toggle('active',el.dataset.id===id);
  });
}
function updatePreview(){
  document.getElementById('de-preview').innerHTML=md(document.getElementById('de-content').value);
}
async function savePage(){
  if(!currentPageId)return;
  await api('PATCH','/api/pages/'+currentPageId,{
    title:document.getElementById('de-title').value,
    content:document.getElementById('de-content').value
  });
}
async function addRootPage(slug){
  await api('POST','/api/projects/'+slug+'/pages',{title:'New Page',content:''});
  toast('Page created','ok');
  setTimeout(()=>render(),200);
}
async function addChildPage(parentId,slug){
  await api('POST','/api/projects/'+slug+'/pages',{title:'New Subpage',content:'',parent_id:parentId});
  toast('Subpage created','ok');
  setTimeout(()=>render(),200);
}
async function deletePage(id,slug){
  if(!confirm('Delete this page and all sub-pages?'))return;
  await api('DELETE','/api/pages/'+id);
  toast('Page deleted','ok');
  setTimeout(()=>render(),200);
}
async function addStandalonePage(){
  const ok=await api('POST','/api/pages',{title:'New Standalone Page',content:''});
  if(ok){toast('Standalone page created','ok');setTimeout(()=>render(),200)}
}

// ── Project Settings ──
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

// ── Agents ──
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
    if(wl.total_tasks)parts.push(`Total: ${wl.total_tasks}`);
    if(wl.done_tasks)parts.push(`Done: ${wl.done_tasks}`);
    if(wl.active_projects?.length)parts.push(`Projects: ${wl.active_projects.join(', ')}`);
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

// ── System Settings ──
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

// ── Public Dashboard (unauthenticated visitors) ──
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

// ── Helpers ──
function esc(s){if(!s)return'';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fmtTime(t){if(!t)return'';let d=new Date(t);if(isNaN(d))d=new Date(t.replace(' ','T')+'Z');const now=new Date();const diff=Math.floor((now-d)/1000);if(diff<60)return'just now';if(diff<3600)return Math.floor(diff/60)+'m ago';if(diff<86400)return Math.floor(diff/3600)+'h ago';return t.slice(0,10)}
const timeAgo=fmtTime;
function writeBtn(html){return isAuthenticated()?html:''}

// ── Init ──
window.addEventListener('hashchange',render);
document.getElementById('menu-toggle').addEventListener('click',()=>{
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebar-overlay').classList.toggle('open');
});
document.getElementById('sidebar-overlay').addEventListener('click',()=>{
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('open');
});
document.getElementById('panel-bg').addEventListener('click',closeTaskPanel);
document.getElementById('modal-bg').addEventListener('click',e=>{if(e.target===e.currentTarget)closeModal()});
const addProjBtn=document.getElementById('add-proj-btn');
if(addProjBtn)addProjBtn.addEventListener('click',e=>{
  e.preventDefault();
  openModal(`<h3>New Project</h3>
    <div class="form-group"><label>Name</label><input id="np-name" placeholder="Project name"></div>
    <div class="form-group"><label>Description</label><textarea id="np-desc" rows="2" placeholder="What is this project about?"></textarea></div>
    <div class="form-group"><div class="field-row"><div><label>Icon</label><input class="icon-inp" id="np-icon" value="📋"></div><div><label>Color</label><input class="color-inp" id="np-color" type="color" value="#3b82f6"></div></div></div>
    <div style="display:flex;gap:8px;justify-content:flex-end"><button class="btn btn-s" onclick="closeModal()">Cancel</button><button class="btn btn-p" onclick="createProject()">Create</button></div>`);
});
async function createProject(){
  const name=document.getElementById('np-name').value.trim();
  if(!name){toast('Name required','err');return}
  await api('POST','/api/projects',{
    name,
    description:document.getElementById('np-desc').value,
    icon:document.getElementById('np-icon').value,
    color:document.getElementById('np-color').value
  });
  closeModal();toast('Project created','ok');
  setTimeout(()=>render(),200);
}

// Global search
document.getElementById('global-search').addEventListener('keydown',e=>{
  if(e.key==='Enter'){
    const q=e.target.value.trim();
    if(q){location.hash='#search?q='+encodeURIComponent(q);e.target.value='';}
  }
});
document.addEventListener('keydown',e=>{
  if((e.metaKey||e.ctrlKey)&&e.key==='k'){
    e.preventDefault();
    const s=document.getElementById('global-search');
    s.focus();s.select();
  }
});

// Search view handler
const origRender=render;
render=async function(){
  const h=location.hash||'#overview';
  if(h.startsWith('#search')){
    const q=new URLSearchParams(h.slice(7)).get('q')||'';
    const app=document.getElementById('app');
    await loadSidebar();
    if(!q){app.innerHTML=`<div class="search-wrap"><div class="search-bar"><input id="search-input" placeholder="Search tasks and pages…" value="" autofocus></div></div>`;
      document.getElementById('search-input')?.addEventListener('keydown',e=>{if(e.key==='Enter')location.hash='#search?q='+encodeURIComponent(e.target.value)});
      return;
    }
    const data=await api('GET','/api/search?q='+encodeURIComponent(q));
    const results=data?.results||[];
    let sh=`<div class="search-wrap"><div class="search-bar"><input id="search-input" placeholder="Search tasks and pages…" value="${esc(q)}" autofocus></div>`;
    sh+=`<div style="font-size:12px;color:var(--t2);margin-bottom:12px">${results.length} results for "${esc(q)}"</div>`;
    sh+=`<div class="search-results">`;
    results.forEach(r=>{
      sh+=`<div class="sr-item" onclick="handleSearchClick('${r.type}','${r.id}','${r.project_slug||''}')">
        <div class="sr-type">${r.type}</div>
        <div class="sr-title">${esc(r.title)}</div>
        <div class="sr-snippet">${r.snippet||''}</div>
        <div class="sr-proj">${esc(r.project_name||'')}</div>
      </div>`;
    });
    if(!results.length)sh+=`<div class="empty"><div class="empty-icon">🔍</div><h3>No results</h3></div>`;
    sh+=`</div></div>`;
    app.innerHTML=sh;
    document.getElementById('search-input')?.addEventListener('keydown',e=>{if(e.key==='Enter')location.hash='#search?q='+encodeURIComponent(e.target.value)});
    return;
  }
  return origRender();
};
function handleSearchClick(type,id,slug){
  if(type==='task')loadAndOpenTask(id);
  else if(type==='page'&&slug)location.hash='#project/'+slug+'/docs';
}

// ── View-aware polling ──
// Docs/Settings/Analytics: never auto-poll (disruptive or unnecessary)
// Board/Overview/Activity/Discussions/Agents: poll at longer intervals
const POLL_CFG={
  docs:false,settings:false,analytics:false,
  board:30000,overview:30000,activity:30000,discussions:30000,agents:60000,
};
let _pollTimer=null,_lastView=null;
function startViewPoll(){
  if(_pollTimer){clearInterval(_pollTimer);_pollTimer=null}
  const{view}=getRoute();
  if(view===_lastView)return;
  _lastView=view;
  const ms=POLL_CFG[view];
  if(!ms)return;
  _pollTimer=setInterval(()=>{if(!S.taskPanelOpen)render()},ms);
}
// Patch render() to restart poll on view change
const _origRender=render;
render=async function(){
  await _origRender();
  startViewPoll();
};

// ── Export/Import ──
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

// ── Analytics ──
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

// ── Discussions ──
async function renderDiscussions(app){
  const data = await api('GET', '/api/discussions?limit=50');
  if(!data) return;
  
  app.innerHTML = `
    <div class="kb-header">
      <h2>💬 Discussions</h2>
      ${isAuthenticated() ? '<button class="btn btn-p btn-sm" onclick="showNewDiscussionModal()">+ New Discussion</button>' : ''}
    </div>
    <div style="padding:0 24px 24px">
      ${data.total === 0 ?
        '<div class="empty"><div class="empty-icon">💬</div><h3>No discussions yet</h3><p>Discussions are used for multi-round agent review of proposals and decisions</p></div>' :
        `<div class="disc-list">${data.discussions.map(d => renderDiscussionItem(d)).join('')}</div>`
      }
    </div>`;
}

function renderDiscussionItem(d){
  const statusCls = d.status==='consensus'?'var(--ok)':d.status==='closed'?'var(--t2)':'var(--ac)';
  const statusLabel = d.status==='consensus'?'✅ Consensus':d.status==='closed'?'🔴 Closed':'🔵 Open';
  const rounds = [];
  for(let i=1;i<=d.max_rounds;i++) rounds.push(`<span style="width:8px;height:8px;border-radius:50%;display:inline-block;background:${i<=d.current_round?'var(--ac)':'var(--bg3)'}"></span>`);
  const parts = d.participants && d.participants.length;
  const partBadges = parts && d.participants.length <= 4 ? d.participants.map(p =>
    `<span style="font-size:10px;background:var(--bg2);border:1px solid var(--bd);border-radius:var(--rs);padding:1px 6px;color:var(--t1)">${p===d.leader?'👑 ':''}${esc(p)}</span>`
  ).join(' ') : '';
  return `<div class="disc-item" onclick="showDiscussion('${d.id}')">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
      ${isAuthenticated()?visBadge(d.visibility):''}
      <span style="font-weight:600;font-size:14px;flex:1">${esc(d.title)}</span>
      <span class="disc-status" style="background:${statusCls};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">${statusLabel}</span>
    </div>
    <div style="display:flex;align-items:center;gap:12px;font-size:12px;color:var(--t2)">
      <span>R${d.current_round}/${d.max_rounds}</span>
      <span>${rounds.join(' ')}</span>
      <span>${d.feedback_count||0} feedback</span>
      ${d.leader ? `<span>👤 ${esc(d.leader)}</span>` : ''}
      ${parts ? `<span>👥 ${d.participants.length} participant${d.participants.length!==1?'s':''}</span>` : ''}
      <span style="margin-left:auto">${timeAgo(d.updated_at||d.created_at)}</span>
    </div>
    ${partBadges ? `<div style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap">${partBadges}</div>` : ''}
  </div>`;
}

async function showDiscussion(id){
  const d = await api('GET', `/api/discussions/${id}`);
  if(!d) return;
  const summary = await api('GET', `/api/discussions/${id}/summary`);

  // Status badge config
  const statusMap = {
    open: {label:'Open', bg:'var(--ac)'},
    closed: {label:'Closed', bg:'var(--t2)'},
    consensus: {label:'Consensus', bg:'var(--ok)'},
  };
  const st = statusMap[d.status] || {label:d.status, bg:'var(--t2)'};

  // Verdict config
  const verdictMap = {
    approve: {icon:'✅', label:'Approve', cls:'verdict-approve'},
    reject: {icon:'❌', label:'Reject', cls:'verdict-reject'},
    conditional: {icon:'💬', label:'Conditional', cls:'verdict-comment'},
  };

  // Global verdict summary
  const allFb = d.feedback || [];
  const totalApprove = allFb.filter(f => f.verdict === 'approve').length;
  const totalReject = allFb.filter(f => f.verdict === 'reject').length;
  const totalComment = allFb.filter(f => f.verdict === 'conditional' || !f.verdict).length;

  // Group feedback by round
  const rounds = {};
  allFb.forEach(fb => {
    const r = fb.round || 1;
    if(!rounds[r]) rounds[r] = [];
    rounds[r].push(fb);
  });

  // Build per-round timeline HTML
  let timelineHtml = '';
  for(let r = 1; r <= d.max_rounds; r++){
    const fbList = rounds[r] || [];
    const hasFeedback = fbList.length > 0;
    const isCurrent = r === d.current_round;
    const isFuture = r > d.current_round;

    timelineHtml += `<div style="margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <span style="font-size:12px;font-weight:700;color:${isCurrent?'var(--ac)':isFuture?'var(--t2)':'var(--t0)'}">
          ${isFuture?'⬜':isCurrent?'🔵':'✅'} Round ${r}
        </span>
        ${isCurrent ? '<span style="font-size:10px;background:var(--ac);color:#fff;padding:1px 6px;border-radius:8px">CURRENT</span>' : ''}
        ${isFuture ? '<span style="font-size:10px;color:var(--t2)">PENDING</span>' : ''}
        ${hasFeedback ? `<span style="font-size:11px;color:var(--t2);margin-left:auto">${fbList.length} response${fbList.length!==1?'s':''}</span>` : ''}
      </div>
      ${fbList.map(fb => {
        const v = verdictMap[fb.verdict] || verdictMap.conditional;
        return `<div class="disc-feedback-item">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
            <span style="font-weight:600;font-size:13px">${esc(fb.participant)}</span>
            ${fb.role ? `<span style="font-size:11px;color:var(--t2)">${esc(fb.role)}</span>` : ''}
            <span class="${v.cls}" style="font-size:11px;font-weight:600;text-transform:uppercase">${v.icon} ${v.label}</span>
            ${fb.word_count ? `<span style="font-size:10px;color:var(--t2)">${fb.word_count} words</span>` : ''}
            <span style="margin-left:auto;font-size:10px;color:var(--t2)">${timeAgo(fb.created_at)}</span>
          </div>
          <div style="font-size:13px;color:var(--t1);line-height:1.6">${md(fb.content||'')}</div>
        </div>`;
      }).join('')}
      ${!hasFeedback && !isFuture ? '<div style="font-size:12px;color:var(--t2);padding:8px 0">No feedback submitted</div>' : ''}
    </div>`;
  }

  // Final outcome
  let outcomeHtml = '';
  if(summary){
    const consensusMap = {
      approved: {label:'✅ Approved', color:'var(--ok)'},
      approved_with_conditions: {label:'⚠️ Approved with Conditions', color:'var(--warn)'},
      rejected: {label:'❌ Rejected', color:'var(--err)'},
      in_progress: {label:'🔄 In Progress', color:'var(--ac)'},
      no_feedback: {label:'⏳ Awaiting Feedback', color:'var(--t2)'},
    };
    const c = consensusMap[summary.consensus] || {label:summary.consensus, color:'var(--t2)'};
    const totalFb = summary.total_feedback || 0;
    const roundsCompleted = Object.keys(rounds).filter(r => rounds[r].length > 0).length;

    outcomeHtml = `<div style="background:var(--bg2);border:1px solid var(--bd);border-radius:var(--r);padding:14px;margin-bottom:16px">
      <div style="font-size:12px;font-weight:600;margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em;color:var(--t2)">Outcome</div>
      <div style="font-size:16px;font-weight:700;color:${c.color};margin-bottom:6px">${c.label}</div>
      <div style="font-size:12px;color:var(--t2);display:flex;gap:16px">
        <span>${totalFb} feedback total</span>
        <span>${roundsCompleted}/${d.max_rounds} rounds completed</span>
        <span>Round ${d.current_round} of ${d.max_rounds}</span>
      </div>
    </div>`;
  }

  const modal = document.getElementById('modal');
  document.getElementById('modal-bg').classList.add('open');
  modal.innerHTML = `
    <div style="max-width:750px;max-height:85vh;overflow-y:auto;padding:24px">
      <button class="btn btn-s btn-sm" onclick="closeModal()" style="margin-bottom:12px">\u2190 Back</button>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <h2 style="flex:1">${esc(d.title)}</h2>
        <span class="disc-status" style="background:${st.bg};color:#fff">${st.label}</span>
        ${isAuthenticated()?`<span class="vis-badge ${d.visibility==='hidden'?'hid':'pub'}" style="cursor:pointer;font-size:14px;opacity:1" title="Click to toggle visibility" onclick="event.stopPropagation();toggleDiscussionVisibility('${d.id}','${d.visibility||'public'}')">${d.visibility==='hidden'?'🚫':'👁️'}</span>`:''}
      </div>
      <div style="font-size:12px;color:var(--t2);margin-bottom:16px;display:flex;flex-wrap:wrap;gap:12px">
        <span>Created by ${esc(d.created_by||'unknown')}</span>
        <span>${timeAgo(d.created_at)}</span>
        ${d.updated_at && d.updated_at !== d.created_at ? `<span>Updated ${timeAgo(d.updated_at)}</span>` : ''}
        ${d.target_type ? `<span>Linked to ${esc(d.target_type)}${d.target_id ? ' '+esc(String(d.target_id)) : ''}</span>` : ''}
      </div>
      ${d.context ? `<div style="background:var(--bg2);border:1px solid var(--bd);border-radius:var(--r);padding:14px;margin-bottom:16px">
        <div style="font-size:12px;font-weight:600;margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em;color:var(--t2)">Context</div>
        <div style="font-size:13px;color:var(--t1);line-height:1.6">${md(d.context)}</div>
      </div>` : ''}
      ${(d.participants && d.participants.length) || d.leader ? `<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:16px">
        ${d.leader ? `<span style="font-size:12px;font-weight:600;color:var(--warn)">👑 ${esc(d.leader)}</span>` : ''}
        ${d.participants && d.participants.length ? d.participants.map(p =>
          `<span style="font-size:11px;background:${p===d.leader?'var(--warn)':'var(--bg2)'};border:1px solid ${p===d.leader?'var(--warn)':'var(--bd)'};border-radius:var(--rs);padding:2px 8px;color:${p===d.leader?'#000':'var(--t1)'};font-weight:${p===d.leader?'600':'400'}">${p===d.leader?'👑 ':''}${esc(p)}</span>`
        ).join(' ') : ''}
      </div>` : ''}
      ${allFb.length > 0 ? `<div class="stats-bar" style="padding:0 0 16px">
        <div class="stat-card" style="padding:10px 14px">
          <div style="display:flex;align-items:center;gap:6px">
            <span style="color:var(--ok);font-size:16px">✅</span>
            <span style="font-weight:600;font-size:18px;color:var(--ok)">${totalApprove}</span>
            <span style="font-size:12px;color:var(--t2)">Approve</span>
          </div>
        </div>
        <div class="stat-card" style="padding:10px 14px">
          <div style="display:flex;align-items:center;gap:6px">
            <span style="color:var(--err);font-size:16px">❌</span>
            <span style="font-weight:600;font-size:18px;color:var(--err)">${totalReject}</span>
            <span style="font-size:12px;color:var(--t2)">Reject</span>
          </div>
        </div>
        <div class="stat-card" style="padding:10px 14px">
          <div style="display:flex;align-items:center;gap:6px">
            <span style="color:var(--ac);font-size:16px">💬</span>
            <span style="font-weight:600;font-size:18px;color:var(--ac)">${totalComment}</span>
            <span style="font-size:12px;color:var(--t2)">Conditional</span>
          </div>
        </div>
        <div class="stat-card" style="padding:10px 14px">
          <div style="display:flex;align-items:center;gap:6px">
            <span style="font-size:16px">📊</span>
            <span style="font-weight:600;font-size:18px">${allFb.length}</span>
            <span style="font-size:12px;color:var(--t2)">Total</span>
          </div>
        </div>
      </div>` : ''}
      ${outcomeHtml}
      ${isAuthenticated() ? `
      <div style="margin-bottom:16px;padding:12px;background:var(--bg2);border-radius:var(--rs);border:1px solid var(--bd)">
        <div style="font-size:12px;font-weight:600;margin-bottom:8px">Add Feedback (Round ${d.current_round})</div>
        <div style="display:flex;gap:8px;margin-bottom:8px">
          <input id="fb-participant" placeholder="Your name" style="flex:1">
          <select id="fb-verdict"><option value="">No verdict</option><option value="approve">✅ Approve</option><option value="conditional">💬 Conditional</option><option value="reject">❌ Reject</option></select>
        </div>
        <textarea id="fb-content" placeholder="Your feedback..." rows="3" style="margin-bottom:8px"></textarea>
        <button class="btn btn-p btn-sm" onclick="submitFeedback('${d.id}')">Submit</button>
      </div>` : ''}
      <div style="border-top:1px solid var(--bd);padding-top:12px">
        <div style="font-size:13px;font-weight:600;margin-bottom:12px">Rounds & Feedback</div>
        ${timelineHtml || '<div class="empty"><div class="empty-icon">💬</div><h3>No feedback yet</h3><p style="font-size:13px;color:var(--t2)">Waiting for participants to respond</p></div>'}
      </div>
    </div>`;
}

async function submitFeedback(discId){
  const participant = document.getElementById('fb-participant').value.trim();
  const content = document.getElementById('fb-content').value.trim();
  const verdict = document.getElementById('fb-verdict').value;
  if(!participant || !content) return toast('Name and content required','err');
  const ok = await api('POST', `/api/discussions/${discId}/feedback`, {participant, content, verdict});
  if(ok) { toast('Feedback added'); showDiscussion(discId); }
  else toast('Failed to add feedback','err');
}

function showNewDiscussionModal(){
  const modal = document.getElementById('modal');
  document.getElementById('modal-bg').classList.add('open');
  modal.innerHTML = `
    <div style="max-width:500px;padding:24px">
      <h2 style="margin-bottom:16px">New Discussion</h2>
      <label style="font-size:12px;color:var(--t2);margin-bottom:4px;display:block">Title</label>
      <input id="nd-title" placeholder="Discussion topic..." style="margin-bottom:12px">
      <label style="font-size:12px;color:var(--t2);margin-bottom:4px;display:block">Context / Description</label>
      <textarea id="nd-context" placeholder="Description or context for this discussion..." rows="3" style="margin-bottom:12px"></textarea>
      <div style="display:flex;gap:12px;margin-bottom:12px">
        <div style="flex:1">
          <label style="font-size:12px;color:var(--t2);margin-bottom:4px;display:block">Leader</label>
          <input id="nd-leader" placeholder="Discussion leader (optional)" style="width:100%">
        </div>
        <div style="width:140px">
          <label style="font-size:12px;color:var(--t2);margin-bottom:4px;display:block">Max Rounds</label>
          <select id="nd-rounds" style="width:100%">
            <option value="3">3 rounds</option><option value="5" selected>5 rounds</option><option value="7">7 rounds</option>
          </select>
        </div>
      </div>
      <label style="font-size:12px;color:var(--t2);margin-bottom:4px;display:block">Participants</label>
      <input id="nd-participants" placeholder="agent1, agent2, agent3 (comma-separated, optional)" style="margin-bottom:16px">
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-s" onclick="closeModal()">Cancel</button>
        <button class="btn btn-p" onclick="createDiscussion()">Create</button>
      </div>
    </div>`;
}

async function createDiscussion(){
  const title = document.getElementById('nd-title').value.trim();
  const max_rounds = parseInt(document.getElementById('nd-rounds').value);
  const context = document.getElementById('nd-context').value.trim();
  const leader = document.getElementById('nd-leader').value.trim();
  const participantsRaw = document.getElementById('nd-participants').value.trim();
  const participants = participantsRaw ? participantsRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
  if(!title) return toast('Title required','err');
  const ok = await api('POST', '/api/discussions', {title, max_rounds, context, leader, participants});
  if(ok) { toast('Discussion created'); closeModal(); render(); }
  else toast('Failed','err');
}

// ── Activity ──
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

// ── Keyboard shortcuts ──
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
