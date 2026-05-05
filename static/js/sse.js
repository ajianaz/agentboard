// // ── SSE Client ──
// Real-time board updates via Server-Sent Events.
// Events are public (only IDs/titles/slugs — no sensitive data).
// Replaces polling for supported views.
let _sse=null,_sseRetry=null;

function connectSSE(){
  if(_sse)return;
  _sse=new EventSource('/api/events');
  _sse.addEventListener('task_created',e=>_onEvent(e));
  _sse.addEventListener('task_updated',e=>_onEvent(e));
  _sse.addEventListener('task_deleted',e=>_onEvent(e));
  _sse.addEventListener('plan_created',e=>_onEvent(e));
  _sse.addEventListener('plan_updated',e=>_onEvent(e));
  _sse.addEventListener('plan_deleted',e=>_onEvent(e));
  _sse.addEventListener('plan_step_updated',e=>_onEvent(e));
  _sse.addEventListener('project_created',()=>{loadSidebar();_scheduleRender()});
  _sse.addEventListener('project_updated',()=>{loadSidebar();_scheduleRender()});
  _sse.addEventListener('project_archived',()=>{loadSidebar();_scheduleRender()});
  _sse.addEventListener('project_restored',()=>{loadSidebar();_scheduleRender()});
  _sse.onerror=()=>{
    _sse.close();_sse=null;
    if(_sseRetry)clearTimeout(_sseRetry);
    _sseRetry=setTimeout(connectSSE,5000);
  };
}

function disconnectSSE(){
  if(_sse){_sse.close();_sse=null}
  if(_sseRetry){clearTimeout(_sseRetry);_sseRetry=null}
}

let _renderTimer=null;
function _scheduleRender(){
  if(S.taskPanelOpen)return;
  if(_renderTimer)clearTimeout(_renderTimer);
  _renderTimer=setTimeout(()=>{render();_renderTimer=null},300);
}

// Auto-connect on page load
connectSSE();
