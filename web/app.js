const state = { status: null, active: null, timer: null, agents: [] };
const $ = (id) => document.getElementById(id);

function token() { return localStorage.getItem("ge360_token") || ""; }
function headers(json=false) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  if (token()) h["Authorization"] = "Bearer " + token();
  return h;
}
async function api(path, options={}) {
  options.headers = {...headers(Boolean(options.body)), ...(options.headers||{})};
  let r = await fetch(path, options);
  if (r.status === 401) {
    const value = prompt("Token GE360 richiesto:");
    if (value !== null) localStorage.setItem("ge360_token", value.trim());
    options.headers = {...headers(Boolean(options.body)), ...(options.headers||{})};
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
  return String(text ?? "").replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
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
  navigator.clipboard.writeText(text).then(()=>{
    if (success) success();
  }).catch(()=>alert("Impossibile copiare automaticamente. Seleziona il testo manualmente."));
}

function renderModels(models) {
  const select=$("model");
  const old=select.value || "gpt-5.6-luna";
  select.innerHTML=models.map(m=>'<option value="'+safe(m.id)+'">'+safe(m.name)+' · '+safe(m.profile)+'</option>').join('');
  if (models.some(m=>m.id===old)) select.value=old;
  else if (models.some(m=>m.id==="gpt-5.6-luna")) select.value="gpt-5.6-luna";
  updateModelNote();
}
function updateModelNote() {
  const models=state.status?.models||[];
  const item=models.find(m=>m.id===$("model").value);
  $("model-note").textContent=item ? item.note : "";
}
function renderAgents(agents, sessions) {
  state.agents=agents||[];
  const jarvisActive=sessions.length>0;
  const master='<article class="agent-card master">'+
    '<div class="agent-top"><div><div class="agent-name">JARVIS</div><div class="agent-role">ORCHESTRATORE CODEX</div></div>'+
    '<span class="agent-status '+(jarvisActive?'active':'ready')+'">'+(jarvisActive?'ATTIVO':'PRONTO')+'</span></div>'+
    '<p>Coordina il lavoro, sceglie quando delegare e raccoglie i risultati degli agenti specializzati.</p>'+
    '<div class="agent-footer"><span>'+(sessions.length? sessions.length+' sessione/i':'nessuna sessione')+'</span></div></article>';

  const cards=state.agents.map((a,i)=>'<article class="agent-card">'+
    '<div class="agent-top"><div><div class="agent-name">'+safe(a.name)+'</div><div class="agent-role">SUBAGENTE CODEX</div></div><span class="agent-status ready">PRONTO</span></div>'+
    '<p>'+safe(a.description||'Agente specializzato GE360')+'</p>'+
    '<div class="agent-footer"><button class="ghost small" data-agent-detail="'+i+'">Dettagli</button><span>'+safe(a.id)+'</span></div></article>').join('');
  $("agents").innerHTML=master+cards;
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
function renderStatus(s) {
  state.status = s;
  $("overall").textContent = "SERVER ONLINE";
  $("overall").className = "status-pill ok";

  const sys=s.system, mem=sys.memory, disk=sys.disk;
  $("metrics").innerHTML =
    metric("CPU / LOAD", sys.cpu_count+" core · "+sys.load[0]) +
    metric("RAM", bytes(mem.used)+" / "+bytes(mem.total)) +
    metric("DISCO", pct(disk.used,disk.total)+"% usato") +
    metric("CODEX", s.codex.installed ? (s.codex.authenticated ? (s.codex.billing_mode==="api" ? "API KEY ⚠" : (s.codex.billing_mode==="chatgpt" ? "CHATGPT" : "LOGIN OK")) : "LOGIN RICHIESTO") : "NON INSTALLATO");

  $("workspace").innerHTML = s.workspaces.map(w=>'<option value="'+safe(w.id)+'">'+safe(w.name)+(w.exists?"":" · MANCANTE")+'</option>').join("");
  renderModels(s.models||[]);
  renderAgents(s.agents||[],s.sessions||[]);

  const aw=$("auth-warning");
  if (!s.codex.installed || !s.codex.authenticated || s.codex.billing_mode==="api") {
    aw.classList.remove("hidden");
    aw.textContent = !s.codex.installed
      ? "Codex CLI non risulta installato. Esegui jarvis login sul Debian."
      : (!s.codex.authenticated
        ? "Codex è installato ma il login non risulta attivo. Esegui jarvis login."
        : "ATTENZIONE: Codex risulta autenticato con API key. Questo può usare fatturazione API separata. Esegui jarvis login per passare a ChatGPT.");
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
    const body={name:$("session-name").value.trim(),workspace_id:$("workspace").value,model:$("model").value};
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
$("toggle-new-agent").onclick=()=>$("new-agent-form").classList.toggle("hidden");
$("create-agent").onclick=createAgent;
$("agent-detail-close").onclick=()=>$("agent-detail-panel").classList.add("hidden");
$("agent-detail-copy").onclick=()=>copyText($("agent-detail-text").textContent,()=>{$("agent-detail-copy").textContent="Copiato";setTimeout(()=>$("agent-detail-copy").textContent="Copia istruzioni",1200);});
$("usage-refresh").onclick=readUsage;
$("usage-copy").onclick=()=>copyText($("usage-output").textContent,()=>{$("usage-copy").textContent="Copiato";setTimeout(()=>$("usage-copy").textContent="Copia",1200);});
$("copy-log").onclick=()=>copyText($("screen").textContent,()=>{$("copy-log").textContent="Copiato";setTimeout(()=>$("copy-log").textContent="Copia log",1200);});
$("refresh-log").onclick=updateScreen;
$("log-session").onchange=()=>{state.active=$("log-session").value||null;$("terminal-title").textContent=state.active||"Nessuna sessione selezionata";updateScreen();};
$("send").onclick=sendPrompt;
$("prompt").addEventListener("keydown",e=>{if((e.ctrlKey||e.metaKey)&&e.key==="Enter")sendPrompt();});

refresh().then(updateScreen);
state.timer=setInterval(()=>{refresh();updateScreen();},3500);
