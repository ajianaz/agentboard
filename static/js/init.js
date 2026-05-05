// // ── Init ──
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


// // ── View-aware polling ──
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


