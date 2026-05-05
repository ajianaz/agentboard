// // ── Overview ──
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


// // ── Inbox ──
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


