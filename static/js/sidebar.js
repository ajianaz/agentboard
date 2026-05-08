// // ── Setup ──
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

// // ── Maintenance banner ──
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


// // ── Sidebar ──
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


