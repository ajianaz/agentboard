// // ── Discussions ──
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


