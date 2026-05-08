// __preamble__

// // ── State ──
let S={projects:[],currentSlug:null,poll:null,taskPanelOpen:false};


// // ── Auth helpers ──
function isAuthenticated(){
  return !!localStorage.getItem('ab_key');
}


// // ── API ──
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


// // ── Toast ──
function toast(msg,type='info'){
  const c=document.getElementById('toast-c');
  const t=document.createElement('div');
  t.className='toast toast-'+type;t.textContent=msg;
  c.appendChild(t);
  setTimeout(()=>t.remove(),3500);
}


// // ── Markdown ──
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


// // ── Modal ──
function openModal(html){
  document.getElementById('modal').innerHTML=html;
  document.getElementById('modal-bg').classList.add('open');
}
function closeModal(){document.getElementById('modal-bg').classList.remove('open')}


// // ── Helpers ──
function esc(s){if(!s)return'';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fmtTime(t){if(!t)return'';let d=new Date(t);if(isNaN(d))d=new Date(t.replace(' ','T')+'Z');const now=new Date();const diff=Math.floor((now-d)/1000);if(diff<60)return'just now';if(diff<3600)return Math.floor(diff/60)+'m ago';if(diff<86400)return Math.floor(diff/3600)+'h ago';return t.slice(0,10)}
const timeAgo=fmtTime;
function writeBtn(html){return isAuthenticated()?html:''}


