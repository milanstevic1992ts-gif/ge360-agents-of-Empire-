const state = {
  status: null,
  active: null,
  timer: null,
  agents: [],
  route: null,
  files: [],
  attachments: new Set()
};
const $ = (id) => document.getElementById(id);

function token() { return localStorage.getItem("ge360_token") || ""; }
function headers(json=false) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  if (token()) h["Authorization"] = "Bearer " + token();
  return h;
}
async function api(path, options={}) {
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  options.headers = {...headers(Boolean(options.body) && !isForm), ...(options.headers||{})};
  let r = await fetch(path, options);
  if (r.status === 401) {
    const value = prompt("Token GE360 richiesto:");
    if (value !== null) localStorage.setItem("ge360_token", value.trim());
    options.headers = {...headers(Boolean(options.body) && !isForm), ...(options.headers||{})};
    r = await fetch(path, options);
  }
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.json();
}
function bytes(n) {
  if (!n) return "0 GB";
  return (n / 1073741824).toFixed(1) + " GB";
}
function pct(used,total) {
  if (!total) return 0;
  return Math.round(used*100/total);
}
function safe(text) {
  return String(text ?? "").replace(/[&<>"']/g, c=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}
function metric(label, value) {
  return '<div class="metric"><div class="label">'+safe(label)+'</div><div class="value">'+safe(value)+'</div></div>';
}
function sessionOptions(sessions, emptyLabel="Nessuna sessione") {
  if (!sessions.length) return '<option value="">'+safe(emptyLabel)+'</option>';
  return sessions.map(s=>'<option value="'+safe(s.name)+'">'+safe(s.name)+(s.model?' · '+safe(s.model):'')+'</option>').join('');
}
function copyText(text, success) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(()=>{ if (success) success(); })
    .catch(()=>alert("Impossibile copiare automaticamente. Seleziona il testo manualmente."));
}
function routeBadge(label,value,cls="") {
  return '<span class="route-badge '+safe(cls)+'"><b>'+safe(label)+'</b> '+safe(value)+'</span>';
}

const AGENT_VISUALS = {
  ge360_sysadmin: {name:"SysAdmin", badge:"SYS", role:"DEBIAN / SYSTEMD", cls:"sys"},
  ge360_docker: {name:"Docker Engineer", badge:"DKR", role:"DOCKER / COMPOSE", cls:"docker"},
  ge360_developer: {name:"Developer", badge:"DEV", role:"CODICE / GIT / TEST", cls:"dev"},
  ge360_crm: {name:"CRM Engineer", badge:"CRM", role:"SUITECRM / MAUTIC", cls:"crm"},
  ge360_data_intake: {name:"Data Intake Engineer", badge:"DATA", role:"CSV / EXCEL / CLEANING", cls:"data"},
  ge360_n8n_engineer: {name:"n8n Engineer", badge:"n8n", role:"N8N SPECIALIST", cls:"n8n"},
  ge360_automation: {name:"Automation", badge:"AUT", role:"INTEGRAZIONI / FLOW", cls:"automation"},
  ge360_wordpress_seo: {name:"WordPress / SEO", badge:"WP", role:"WORDPRESS / SEO", cls:"wp"}
};
function agentVisual(id, fallback="") {
  return AGENT_VISUALS[id] || {
    name: fallback || id || "Agente",
    badge: (id || "AI").replace("ge360_","").slice(0,3).toUpperCase(),
    role: "SUBAGENTE CODEX",
    cls: "custom"
  };
}
function agentDisplayName(id) {
  const found=state.agents.find(a=>a.id===id);
  return agentVisual(id, found?.name).name;
}

function formatSize(n) {
  if (n < 1024) return n+" B";
  if (n < 1048576) return (n/1024).toFixed(1)+" KB";
  return (n/1048576).toFixed(1)+" MB";
}
function renderFiles(files) {
  state.files=files||[];
  const box=$("file-list");
  if(!box) return;
  const existingIds=new Set(state.files.filter(f=>f.exists).map(f=>f.id));
  state.attachments.forEach(id=>{ if(!existingIds.has(id)) state.attachments.delete(id); });
  if(window.renderChatAttachmentChips) window.renderChatAttachmentChips();
  if(!state.files.length) {
    box.innerHTML='<div class="sub">Nessun file caricato.</div>';
    return;
  }
  box.innerHTML=state.files.map(f=>{
    const checked=state.attachments.has(f.id) ? " checked" : "";
    const missing=f.exists ? "" : " missing";
    return '<label class="file-row'+missing+'">'+
      '<input type="checkbox" data-file-id="'+safe(f.id)+'"'+checked+(f.exists?'':' disabled')+'>'+
      '<div class="file-main"><b>'+safe(f.original_name)+'</b><div class="tiny">'+formatSize(Number(f.size_bytes||0))+' · '+safe(f.uploaded_at||'')+'</div></div>'+
      '<span class="file-state">'+(f.exists?'allegabile':'mancante')+'</span>'+
      '</label>';
  }).join('');
  document.querySelectorAll("[data-file-id]").forEach(el=>{
    el.onchange=()=>{
      const id=el.getAttribute("data-file-id");
      if(el.checked) state.attachments.add(id); else state.attachments.delete(id);
      state.route=null;
      if(window.renderChatAttachmentChips) window.renderChatAttachmentChips();
    };
  });
}
async function refreshFiles() {
  try {
    const r=await api("/api/files");
    renderFiles(r.files||[]);
  } catch(e) {
    const box=$("file-list");
    if(box) box.innerHTML='<div class="sub">Errore allegati: '+safe(e.message)+'</div>';
  }
}
async function uploadFiles(fileList) {
  const files=Array.from(fileList||[]);
  if(!files.length) return;
  const form=new FormData();
  files.forEach(f=>form.append("files",f));
  const button=$("pick-files");
  if(button) button.textContent="Caricamento…";
  try {
    const r=await api("/api/files",{method:"POST",body:form});
    (r.files||[]).forEach(f=>state.attachments.add(f.id));
    await refreshFiles();
    state.route=null;
  } catch(e) {
    alert(e.message);
  } finally {
    if(button) button.textContent="+ Allega file";
    if($("file-input")) $("file-input").value="";
  }
}

function renderModels(models) {
  const select=$("model");
  const old=select.value || "gpt-5.6-luna";
  select.innerHTML=models.map(m=>'<option value="'+safe(m.id)+'">'+safe(m.name)+' · '+safe(m.profile)+'</option>').join('');
  if (models.some(m=>m.id===old)) select.value=old;
  else if (models.some(m=>m.id==="gpt-5.6-luna")) select.value="gpt-5.6-luna";
  updateModelNote();
}
function renderEfforts(efforts) {
  const select=$("effort");
  const old=select.value || "low";
  select.innerHTML=(efforts||[]).map(e=>'<option value="'+safe(e.id)+'">'+safe(e.name)+'</option>').join('');
  if ((efforts||[]).some(e=>e.id===old)) select.value=old;
  else select.value="low";
  updateModelNote();
}
function updateModelNote() {
  const models=state.status?.models||[];
  const efforts=state.status?.reasoning_efforts||[];
  const model=models.find(m=>m.id===$("model").value);
  const effort=efforts.find(e=>e.id===$("effort").value);
  $("model-note").textContent=[
    model ? model.note : "",
    effort ? "Ragionamento "+effort.name.toLowerCase()+": "+effort.note : ""
  ].filter(Boolean).join(" · ");
}
function renderRecipes(recipes) {
  const select=$("recipe");
  const old=select.value;
  const options=['<option value="">Playbook rapido…</option>'].concat(
    (recipes||[]).map(r=>'<option value="'+safe(r.id)+'">'+safe(r.name)+' · '+safe(r.agent)+'</option>')
  );
  select.innerHTML=options.join("");
  if((recipes||[]).some(r=>r.id===old)) select.value=old;
}
function loadRecipe() {
  const recipe=(state.status?.recipes||[]).find(r=>r.id===$("recipe").value);
  if(!recipe) return;
  $("smart-task").value=recipe.prompt;
  state.route=null;
  $("route-primary").textContent=recipe.name;
  $("route-details").innerHTML=
    routeBadge("Agente",recipe.agent)+
    routeBadge("Modello",recipe.model)+
    routeBadge("Rischio",recipe.risk,recipe.risk);
  $("route-reason").textContent=recipe.description;
  $("route-result").classList.remove("empty");
}
function renderRoute(route) {
  state.route=route;
  $("route-primary").textContent="Agente principale: "+agentDisplayName(route.primary_agent);
  const collaboratorNames=(route.collaborators||[]).length
    ? route.collaborators.map(agentDisplayName).join(", ")
    : "nessuno";
  $("route-details").innerHTML=
    routeBadge("Collaboratori",collaboratorNames)+
    routeBadge("Modello",route.model)+
    routeBadge("Reasoning",route.effort)+
    routeBadge("Rischio",route.risk,route.risk);
  $("route-reason").textContent=route.reason||"";
  $("route-result").classList.remove("empty");
}
async function analyzeTask() {
  const task=$("smart-task").value.trim();
  if(!task) {
    alert("Descrivi prima il lavoro.");
    return null;
  }
  $("route-primary").textContent="Analisi locale…";
  $("route-details").innerHTML="";
  $("route-reason").textContent="";
  try {
    const r=await api("/api/smart/route",{method:"POST",body:JSON.stringify({task,attachments:[...state.attachments]})});
    renderRoute(r.route);
    return r.route;
  } catch(e) {
    $("route-primary").textContent="Errore";
    $("route-reason").textContent=e.message;
    return null;
  }
}
async function smartLaunch() {
  const task=$("smart-task").value.trim();
  if(!task) return alert("Descrivi prima il lavoro.");
  try {
    if(!state.route) {
      const analyzed=await analyzeTask();
      if(!analyzed) return;
    }
    const body={
      task,
      workspace_id:$("workspace").value,
      name:"",
      attachments:[...state.attachments]
    };
    const r=await api("/api/smart/launch",{method:"POST",body:JSON.stringify(body)});
    state.active=r.name;
    renderRoute(r.route);
    await refresh();
    await updateScreen();
    $("terminal-panel").scrollIntoView({behavior:"smooth",block:"start"});
  } catch(e) { alert(e.message); }
}

function renderAgents(agents, sessions) {
  state.agents=agents||[];
  const jarvisActive=sessions.length>0;
  const searchInput=$("agent-search");
  const query=(searchInput ? searchInput.value : "").trim().toLowerCase();
  if ($("agent-count")) {
    $("agent-count").textContent=state.agents.length+" agenti + JARVIS";
  }

  const master='<article class="agent-card master">'+
    '<div class="agent-top"><div class="agent-identity"><div class="agent-avatar jarvis-avatar">J</div><div><div class="agent-name">JARVIS</div><div class="agent-role">ORCHESTRATORE CODEX</div></div></div>'+
    '<span class="agent-status '+(jarvisActive?'active':'ready')+'">'+(jarvisActive?'ATTIVO':'PRONTO')+'</span></div>'+
    '<p>Coordina, instrada il lavoro, sceglie i subagenti e raccoglie il risultato finale.</p>'+
    '<div class="agent-footer"><span>'+(sessions.length? sessions.length+' sessione/i':'nessuna sessione')+'</span><span class="agent-id">master</span></div></article>';

  const visible=state.agents
    .map((a,i)=>({a,i}))
    .filter(({a})=>{
      if(!query) return true;
      const v=agentVisual(a.id,a.name);
      return [a.id,a.name,a.description,v.name,v.role].join(" ").toLowerCase().includes(query);
    });

  const cards=visible.map(({a,i})=>{
    const v=agentVisual(a.id,a.name);
    return '<article class="agent-card agent-'+safe(v.cls)+'">'+
      '<div class="agent-top"><div class="agent-identity"><div class="agent-avatar">'+safe(v.badge)+'</div><div><div class="agent-name">'+safe(v.name)+'</div><div class="agent-role">'+safe(v.role)+'</div></div></div><span class="agent-status '+safe(a.status||'ready')+'">'+safe((a.status||'ready').toUpperCase())+'</span></div>'+
      '<p>'+safe(a.description||'Agente specializzato GE360')+'</p>'+
      '<div class="agent-footer"><button class="ghost small" data-agent-detail="'+i+'">Dettagli</button><span class="agent-id">'+safe(a.id)+'</span></div></article>';
  }).join('');

  const empty=query && !visible.length
    ? '<div class="agent-empty">Nessun agente corrisponde a “'+safe(query)+'”.</div>'
    : '';

  $("agents").innerHTML=master+cards+empty;
  document.querySelectorAll("[data-agent-detail]").forEach(btn=>{
    btn.onclick=()=>showAgentDetail(Number(btn.getAttribute("data-agent-detail")));
  });
}
function showAgentDetail(index) {
  const a=state.agents[index];
  if(!a) return;
  $("agent-detail-title").textContent=a.name;
  $("agent-detail-description").textContent=a.description||"";
  $("agent-detail-text").textContent=a.instructions||"Nessuna istruzione disponibile.";
  $("agent-detail-panel").classList.remove("hidden");
  $("agent-detail-panel").scrollIntoView({behavior:"smooth",block:"start"});
}
function renderAgentTimeline(events) {
  const box=$("agent-timeline");
  if(!box) return;
  const list=(events||[]).slice(0,30);
  if(!list.length) {
    box.innerHTML='<div class="sub">La timeline si popolerà quando avvierai un incarico Smart.</div>';
    return;
  }
  box.innerHTML=list.map(e=>{
    const visual=agentVisual(e.agent_id,e.agent_id);
    return '<div class="timeline-row">'+
      '<div class="timeline-dot '+safe(e.status||'ready')+'"></div>'+
      '<div class="timeline-main"><div><b>'+safe(visual.name)+'</b> <span class="timeline-status '+safe(e.status||'ready')+'">'+safe((e.status||'ready').toUpperCase())+'</span></div>'+
      '<div class="sub">'+safe(e.detail||e.event_type||'Evento agente')+'</div>'+
      '<div class="tiny">'+safe(e.session)+' · '+safe(e.event_type)+' · '+safe(e.created_at)+'</div></div>'+
      '</div>';
  }).join('');
}

function renderSmartMemory(smart) {
  const stats=smart?.stats||[];
  $("smart-stats").innerHTML=stats.length ? stats.map(x=>{
    const good=Number(x.good||0), bad=Number(x.bad||0), total=Number(x.total||0);
    return '<div class="memory-stat"><b>'+safe(x.primary_agent)+'</b><span>'+total+' incarichi · '+good+' ✓ · '+bad+' △</span></div>';
  }).join("") : '<div class="sub">La memoria operativa inizierà a popolarsi dopo il primo avvio Smart.</div>';

  const events=smart?.events||[];
  $("activity").innerHTML=events.length ? events.map(e=>{
    const rating=e.rating===1?'✓ riuscito':(e.rating===-1?'△ da migliorare':'in attesa feedback');
    return '<div class="activity-row">'+
      '<div class="activity-main"><div><b>'+safe(e.primary_agent)+'</b> <span class="route-badge '+safe(e.risk)+'">'+safe(e.risk)+'</span></div>'+
      '<div class="sub">'+safe(e.task_preview)+'</div>'+
      '<div class="tiny">'+safe(e.session)+' · '+safe(e.model)+' · '+safe(e.created_at)+'</div></div>'+
      '<div class="activity-feedback"><span class="tiny">'+safe(rating)+'</span>'+
      '<button class="ghost tiny-button" data-feedback-session="'+safe(e.session)+'" data-rating="1">✓</button>'+
      '<button class="ghost tiny-button" data-feedback-session="'+safe(e.session)+'" data-rating="-1">△</button></div></div>';
  }).join("") : '<div class="sub">Nessun incarico Smart ancora.</div>';

  document.querySelectorAll("[data-feedback-session]").forEach(btn=>{
    btn.onclick=()=>sendFeedback(btn.getAttribute("data-feedback-session"),Number(btn.getAttribute("data-rating")));
  });
}
async function sendFeedback(session,rating) {
  try {
    await api("/api/smart/feedback",{method:"POST",body:JSON.stringify({session,rating})});
    await refresh();
  } catch(e) { alert(e.message); }
}

function renderStatus(s) {
  state.status = s;
  if ($("release-version")) $("release-version").textContent="v"+(s.release?.version||"?");
  $("overall").textContent = "SERVER ONLINE";
  $("overall").className = "status-pill ok";

  const sys=s.system, mem=sys.memory, disk=sys.disk;
  $("metrics").innerHTML =
    metric("CPU / LOAD", sys.cpu_count+" core · "+sys.load[0]) +
    metric("RAM", bytes(mem.used)+" / "+bytes(mem.total)) +
    metric("DISCO", pct(disk.used,disk.total)+"% usato") +
    metric("CODEX", s.codex.installed ? (s.codex.authenticated ? (s.codex.billing_mode==="api" ? "API KEY ⚠" : (s.codex.billing_mode==="chatgpt" ? "CHATGPT" : "LOGIN OK")) : "LOGIN RICHIESTO") : "NON INSTALLATO");

  const currentWorkspace=$("workspace").value;
  $("workspace").innerHTML = s.workspaces.map(w=>'<option value="'+safe(w.id)+'">'+safe(w.name)+(w.exists?"":" · MANCANTE")+'</option>').join("");
  if(s.workspaces.some(w=>w.id===currentWorkspace)) $("workspace").value=currentWorkspace;

  renderModels(s.models||[]);
  renderEfforts(s.reasoning_efforts||[]);
  renderRecipes(s.recipes||[]);
  renderAgents(s.agents||[],s.sessions||[]);
  renderAgentTimeline(s.agent_timeline||[]);
  renderSmartMemory(s.smart||{});

  const aw=$("auth-warning");
  if (!s.codex.installed || !s.codex.authenticated || s.codex.billing_mode==="api") {
    aw.classList.remove("hidden");
    aw.textContent = !s.codex.installed
      ? "Codex CLI non risulta installato. Esegui jarvis login sul Debian."
      : (!s.codex.authenticated
        ? "Codex è installato ma il login non risulta attivo. Esegui jarvis login."
        : "ATTENZIONE: Codex risulta autenticato con API key. Questo può usare fatturazione API separata.");
  } else {
    aw.classList.add("hidden");
  }

  const sessions=s.sessions||[];
  if (sessions.length) {
    $("sessions").innerHTML = sessions.map(sess=>'<div class="session">'+
      '<div><div class="session-name"><span class="dot"></span>'+safe(sess.name)+'</div><div class="sub">'+safe(sess.model||'modello non registrato')+' · tmux persistente</div></div>'+
      '<div class="row-actions"><button class="ghost small" data-open="'+safe(sess.name)+'">Log</button><button class="ghost small" data-stop="'+safe(sess.name)+'">Stop</button></div></div>').join("");
  } else {
    $("sessions").innerHTML = '<div class="sub">Nessuna sessione attiva.</div>';
  }
  document.querySelectorAll("[data-open]").forEach(btn=>btn.onclick=()=>openSession(btn.getAttribute("data-open")));
  document.querySelectorAll("[data-stop]").forEach(btn=>btn.onclick=()=>stopSession(btn.getAttribute("data-stop")));

  const logOld=$("log-session").value;
  const usageOld=$("usage-session").value;
  $("log-session").innerHTML=sessionOptions(sessions);
  $("usage-session").innerHTML=sessionOptions(sessions);
  if(sessions.some(x=>x.name===logOld)) $("log-session").value=logOld;
  if(sessions.some(x=>x.name===usageOld)) $("usage-session").value=usageOld;
  if(!state.active && sessions.length) state.active=$("log-session").value;
  if(state.active && sessions.some(x=>x.name===state.active)) $("log-session").value=state.active;
  if(state.active && !sessions.some(x=>x.name===state.active)) state.active=sessions.length?sessions[0].name:null;
  $("terminal-title").textContent=state.active||"Nessuna sessione selezionata";

  let serviceRows = s.services.map(x=>'<div class="service"><span><span class="dot '+(x.state==="active"?"":"off")+'"></span>'+safe(x.name)+'</span><span class="sub">'+safe(x.state)+'</span></div>').join("");
  let dockerRows = (s.docker.containers||[]).slice(0,18).map(x=>'<div class="docker-row"><div><b>'+safe(x.name)+'</b><div class="sub">'+safe(x.image)+'</div></div><span class="sub">'+safe(x.status)+'</span></div>').join("");
  $("services").innerHTML = serviceRows + (dockerRows ? '<div class="eyebrow" style="margin-top:16px">DOCKER</div>'+dockerRows : "");
}
async function refresh() {
  try {
    renderStatus(await api("/api/status"));
  } catch(e) {
    $("overall").textContent="OFFLINE / ACCESSO";
    $("overall").className="status-pill bad";
    console.error(e);
  }
}
async function createSession() {
  try {
    const body={
      name:$("session-name").value.trim(),
      workspace_id:$("workspace").value,
      model:$("model").value,
      effort:$("effort").value
    };
    const r=await api("/api/sessions",{method:"POST",body:JSON.stringify(body)});
    state.active=r.name;
    await refresh();
    await updateScreen();
    $("terminal-panel").scrollIntoView({behavior:"smooth",block:"start"});
  } catch(e) { alert(e.message); }
}
async function createAgent() {
  try {
    const body={id:$("new-agent-id").value.trim(),description:$("new-agent-description").value.trim()};
    const r=await api("/api/agents",{method:"POST",body:JSON.stringify(body)});
    $("new-agent-id").value="";
    $("new-agent-description").value="";
    $("new-agent-form").classList.add("hidden");
    alert(r.note||"Agente creato.");
    await refresh();
  } catch(e) { alert(e.message); }
}
async function openSession(name) {
  state.active=name;
  $("log-session").value=name;
  $("terminal-title").textContent=name;
  await updateScreen();
  $("terminal-panel").scrollIntoView({behavior:"smooth",block:"start"});
}
async function updateScreen() {
  if (!state.active) {
    $("screen").textContent="Avvia o seleziona una sessione JARVIS.";
    return;
  }
  try {
    const r=await api("/api/sessions/"+encodeURIComponent(state.active)+"/screen?lines=350");
    const pre=$("screen");
    pre.textContent=r.screen || "Sessione attiva, nessun output.";
    pre.scrollTop=pre.scrollHeight;
  } catch(e) { $("screen").textContent=e.message; }
}
async function sendPrompt() {
  if (!state.active) return alert("Seleziona prima una sessione JARVIS.");
  const text=$("prompt").value.trim();
  if (!text) return;
  try {
    await api("/api/sessions/"+encodeURIComponent(state.active)+"/message",{method:"POST",body:JSON.stringify({text})});
    $("prompt").value="";
    setTimeout(updateScreen,450);
  } catch(e) { alert(e.message); }
}
async function readUsage() {
  const name=$("usage-session").value;
  if(!name) return alert("Nessuna sessione Codex attiva.");
  $("usage-state").textContent="Lettura…";
  try {
    const r=await api("/api/sessions/"+encodeURIComponent(name)+"/usage",{method:"POST"});
    $("usage-output").textContent=r.screen||"Nessun dato restituito da /status.";
    $("usage-note").textContent=r.note||"Output /status aggiornato.";
    $("usage-state").textContent="Dati reali /status";
    $("usage-output").scrollTop=$("usage-output").scrollHeight;
    if(state.active===name) setTimeout(updateScreen,250);
  } catch(e) {
    $("usage-state").textContent="Errore";
    $("usage-note").textContent=e.message;
  }
}
async function stopSession(name) {
  if (!confirm("Fermare la sessione "+name+"?")) return;
  try {
    await api("/api/sessions/"+encodeURIComponent(name),{method:"DELETE"});
    if (state.active===name) state.active=null;
    await refresh();
    await updateScreen();
  } catch(e) { alert(e.message); }
}

$("refresh").onclick=refresh;
$("create").onclick=createSession;
$("model").onchange=updateModelNote;
$("effort").onchange=updateModelNote;
$("pick-files").onclick=()=>$("file-input").click();
$("file-input").onchange=()=>uploadFiles($("file-input").files);
$("refresh-files").onclick=refreshFiles;
$("load-recipe").onclick=loadRecipe;
$("analyze-task").onclick=analyzeTask;
$("smart-launch").onclick=smartLaunch;
$("smart-task").oninput=()=>{ state.route=null; };
$("toggle-new-agent").onclick=()=>$("new-agent-form").classList.toggle("hidden");
if ($("agent-search")) {
  $("agent-search").oninput=()=>renderAgents(state.agents,state.status?.sessions||[]);
}
$("create-agent").onclick=createAgent;
$("agent-detail-close").onclick=()=>$("agent-detail-panel").classList.add("hidden");
$("agent-detail-copy").onclick=()=>copyText($("agent-detail-text").textContent,()=>{
  $("agent-detail-copy").textContent="Copiato";
  setTimeout(()=>$("agent-detail-copy").textContent="Copia istruzioni",1200);
});
$("usage-refresh").onclick=readUsage;
$("usage-copy").onclick=()=>copyText($("usage-output").textContent,()=>{
  $("usage-copy").textContent="Copiato";
  setTimeout(()=>$("usage-copy").textContent="Copia",1200);
});
$("copy-log").onclick=()=>copyText($("screen").textContent,()=>{
  $("copy-log").textContent="Copiato";
  setTimeout(()=>$("copy-log").textContent="Copia log",1200);
});
$("refresh-log").onclick=updateScreen;
$("log-session").onchange=()=>{
  state.active=$("log-session").value||null;
  $("terminal-title").textContent=state.active||"Nessuna sessione selezionata";
  updateScreen();
};
$("send").onclick=sendPrompt;
$("prompt").addEventListener("keydown",e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==="Enter") sendPrompt();
});

Promise.all([refresh(),refreshFiles()]).then(updateScreen);
state.timer=setInterval(()=>{refresh();updateScreen();},3500);
