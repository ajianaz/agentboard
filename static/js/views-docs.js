// // ── Docs Hub (standalone, cross-project, read-only) ──
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


// // ── Documents (project-scoped, editable) ──
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


