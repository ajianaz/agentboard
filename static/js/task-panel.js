// // ── Task Panel ──
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


// // ── Visibility helpers ──
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


