// // ── Kanban Board ──
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


// // ── Tree View ──
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


// // Drag and drop
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


