const state = { status: null, active: null, timer: null };
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

  $("workspace").innerHTML = s.workspaces.map(function(w) {
    return '<option value="'+safe(w.id)+'">'+safe(w.name)+(w.exists?"":" · MANCANTE")+'</option>';
  }).join("");

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

  if (s.sessions.length) {
    $("sessions").innerHTML = s.sessions.map(function(sess) {
      return '<div class="session">'+
        '<div><div class="session-name"><span class="dot"></span>'+safe(sess.name)+'</div><div class="sub">tmux persistente</div></div>'+
        '<div class="row-actions">'+
          '<button class="ghost small" data-open="'+safe(sess.name)+'">Apri</button>'+
          '<button class="ghost small" data-stop="'+safe(sess.name)+'">Stop</button>'+
        '</div></div>';
    }).join("");
  } else {
    $("sessions").innerHTML = '<div class="sub">Nessuna sessione attiva.</div>';
  }

  document.querySelectorAll("[data-open]").forEach(function(btn) {
    btn.onclick = function() { openSession(btn.getAttribute("data-open")); };
  });
  document.querySelectorAll("[data-stop]").forEach(function(btn) {
    btn.onclick = function() { stopSession(btn.getAttribute("data-stop")); };
  });

  let serviceRows = s.services.map(function(x) {
    return '<div class="service"><span><span class="dot '+(x.state==="active"?"":"off")+'"></span>'+safe(x.name)+'</span><span class="sub">'+safe(x.state)+'</span></div>';
  }).join("");
  let dockerRows = (s.docker.containers||[]).slice(0,18).map(function(x) {
    return '<div class="docker-row"><div><b>'+safe(x.name)+'</b><div class="sub">'+safe(x.image)+'</div></div><span class="sub">'+safe(x.status)+'</span></div>';
  }).join("");
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
    const body={name:$("session-name").value.trim(),workspace_id:$("workspace").value};
    const r=await api("/api/sessions",{method:"POST",body:JSON.stringify(body)});
    await refresh();
    openSession(r.name);
  } catch(e) {
    alert(e.message);
  }
}
async function openSession(name) {
  state.active=name;
  $("terminal-title").textContent=name;
  $("terminal-panel").classList.remove("hidden");
  await updateScreen();
  $("terminal-panel").scrollIntoView({behavior:"smooth",block:"start"});
}
async function updateScreen() {
  if (!state.active) return;
  try {
    const r=await api("/api/sessions/"+encodeURIComponent(state.active)+"/screen?lines=220");
    const pre=$("screen");
    pre.textContent=r.screen || "Sessione attiva, nessun output.";
    pre.scrollTop=pre.scrollHeight;
  } catch(e) {
    $("screen").textContent=e.message;
  }
}
async function sendPrompt() {
  if (!state.active) return;
  const text=$("prompt").value.trim();
  if (!text) return;
  try {
    await api("/api/sessions/"+encodeURIComponent(state.active)+"/message",{method:"POST",body:JSON.stringify({text:text})});
    $("prompt").value="";
    setTimeout(updateScreen,450);
  } catch(e) {
    alert(e.message);
  }
}
async function stopSession(name) {
  if (!confirm("Fermare la sessione "+name+"?")) return;
  try {
    await api("/api/sessions/"+encodeURIComponent(name),{method:"DELETE"});
    if (state.active===name) {
      state.active=null;
      $("terminal-panel").classList.add("hidden");
    }
    refresh();
  } catch(e) {
    alert(e.message);
  }
}
$("refresh").onclick=refresh;
$("create").onclick=createSession;
$("send").onclick=sendPrompt;
$("close-terminal").onclick=function(){state.active=null;$("terminal-panel").classList.add("hidden");};
$("prompt").addEventListener("keydown",function(e){if((e.ctrlKey||e.metaKey)&&e.key==="Enter")sendPrompt();});
refresh();
state.timer=setInterval(function(){refresh();updateScreen();},3000);
