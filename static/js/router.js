// // ── Router ──
function getRoute(){
  const h=location.hash||'#overview';
  if(h==='#overview')return{view:'overview'};
  if(h.startsWith('#docs/')){const s=h.split('/')[1];return{view:'docs',slug:s}}
  if(h==='#docs')return{view:'docs'};
  if(h==='#plans')return{view:'plans'};
  if(h.startsWith('#plans?'))return{view:'plans'};
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
    case'plans':await renderPlans(app,slug);break;
    case'discussions':await renderDiscussions(app);break;
    case'activity':await renderActivity(app);break;
    case'inbox':await renderInbox(app);break;
    default:app.innerHTML=`<div class="empty"><div class="empty-icon">🔍</div><h3>Not found</h3><p>This view doesn't exist</p></div>`;
  }
}


