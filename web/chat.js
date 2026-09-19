(function () {
  "use strict";

  const chatState = {
    thread: null,
    threads: [],
    messages: new Map(),
    abort: null,
    status: "idle"
  };

  function el(id) { return document.getElementById(id); }

  function htmlText(value) {
    let text = safe(String(value == null ? "" : value));
    text = text.replace(/\n/g, "<br>");
    return text;
  }

  function selectedFiles() {
    if (!window.state && typeof state === "undefined") return [];
    return (state.files || []).filter(function (file) {
      return state.attachments.has(file.id) && file.exists;
    });
  }

  function renderAttachmentChips() {
    const box = el("chat-attachments");
    if (!box) return;
    const files = selectedFiles();
    box.innerHTML = files.map(function (file) {
      return '<span class="chat-attachment-chip"><span>📎 ' + safe(file.original_name) +
        '</span><button type="button" data-chat-remove-file="' + safe(file.id) +
        '" aria-label="Rimuovi allegato">×</button></span>';
    }).join("");

    box.querySelectorAll("[data-chat-remove-file]").forEach(function (button) {
      button.onclick = function () {
        const id = button.getAttribute("data-chat-remove-file");
        state.attachments.delete(id);
        document.querySelectorAll("[data-file-id]").forEach(function (checkbox) {
          if (checkbox.getAttribute("data-file-id") === id) checkbox.checked = false;
        });
        renderAttachmentChips();
      };
    });
  }
  window.renderChatAttachmentChips = renderAttachmentChips;

  function toolTitle(message) {
    const meta = message.meta || {};
    const type = meta.item_type || "";
    if (type === "commandExecution") return "Comando";
    if (type === "fileChange") return "Modifica file";
    if (type === "mcpToolCall") return "Strumento";
    if (type === "webSearch") return "Ricerca";
    if (message.kind === "plan") return "Piano";
    return "Attività";
  }

  function attachmentHtml(message) {
    const list = ((message.meta || {}).attachments || []);
    if (!list.length) return "";
    return '<div class="chat-msg-attachments">' +
      list.map(function (name) { return "<span>📎 " + safe(name) + "</span>"; }).join("") +
      "</div>";
  }

  function approvalHtml(message) {
    const meta = message.meta || {};
    const requestId = String(meta.request_id || "");
    const params = meta.params || {};
    const reason = params.reason || "";
    const pending = message.status === "pending";
    const simple = meta.method === "item/commandExecution/requestApproval" ||
      meta.method === "item/fileChange/requestApproval";

    let actions = "";
    if (pending && simple) {
      actions =
        '<div class="approval-actions">' +
        '<button class="primary small" data-chat-approval="' + safe(requestId) + '" data-chat-decision="accept">Approva</button>' +
        '<button class="ghost small" data-chat-approval="' + safe(requestId) + '" data-chat-decision="acceptForSession">Approva sessione</button>' +
        '<button class="ghost small" data-chat-approval="' + safe(requestId) + '" data-chat-decision="decline">Rifiuta</button>' +
        "</div>";
    }

    return '<article id="chat-msg-' + Number(message.id || 0) + '" class="chat-message tool-card approval-card">' +
      '<div class="tool-card-head"><span>APPROVAZIONE RICHIESTA</span><span class="tool-status ' +
      safe(message.status || "pending") + '">' + safe(message.status || "pending") + "</span></div>" +
      '<div class="tool-card-title">' + htmlText(message.content || "Operazione richiesta") + "</div>" +
      (reason ? '<div class="tool-card-note">' + htmlText(reason) + "</div>" : "") +
      actions + "</article>";
  }

  function inputRequestHtml(message) {
    const meta = message.meta || {};
    const requestId = String(meta.request_id || "");
    const questions = Array.isArray(meta.questions) ? meta.questions : [];
    const fields = questions.map(function (question) {
      const options = Array.isArray(question.options) ? question.options : [];
      const hints = options.length
        ? '<div class="chat-option-hints">' + options.map(function (option) {
            return "<span>" + safe(option.label || option.description || option.value || "") + "</span>";
          }).join("") + "</div>"
        : "";
      return '<label class="chat-question"><span>' + safe(question.header || "JARVIS") + "</span>" +
        "<b>" + safe(question.question || "Risposta richiesta") + "</b>" +
        hints +
        '<input type="' + (question.isSecret ? "password" : "text") +
        '" data-chat-answer-request="' + safe(requestId) +
        '" data-chat-answer-question="' + safe(question.id || "") +
        '" placeholder="Scrivi la risposta…"></label>';
    }).join("");

    return '<article id="chat-msg-' + Number(message.id || 0) + '" class="chat-message tool-card approval-card">' +
      '<div class="tool-card-head"><span>JARVIS HA BISOGNO DI TE</span><span class="tool-status ' +
      safe(message.status || "pending") + '">' + safe(message.status || "pending") + "</span></div>" +
      fields +
      (message.status === "pending"
        ? '<button class="primary small" data-chat-answer-submit="' + safe(requestId) + '">Invia risposta</button>'
        : "") +
      "</article>";
  }

  function messageHtml(message) {
    const id = Number(message.id || 0);
    const role = message.role || "assistant";
    const kind = message.kind || "message";
    const status = message.status || "completed";

    if (kind === "approval") return approvalHtml(message);
    if (kind === "input_request") return inputRequestHtml(message);

    if (kind === "reasoning") {
      return '<details id="chat-msg-' + id + '" class="chat-message reasoning-card"' +
        (status === "in_progress" ? " open" : "") + ">" +
        '<summary><span class="thinking-dot"></span> Attività JARVIS</summary>' +
        '<div class="reasoning-body">' + htmlText(message.content || "") + "</div></details>";
    }

    if (kind === "tool" || kind === "plan") {
      return '<article id="chat-msg-' + id + '" class="chat-message tool-card">' +
        '<div class="tool-card-head"><span>' + safe(toolTitle(message)) + '</span><span class="tool-status ' +
        safe(status) + '">' + safe(status) + "</span></div>" +
        '<div class="tool-card-body">' + htmlText(message.content || "") + "</div></article>";
    }

    if (kind === "error" || role === "system") {
      return '<article id="chat-msg-' + id + '" class="chat-message system-message ' +
        (kind === "error" ? "error" : "") + '">' + htmlText(message.content || "") + "</article>";
    }

    if (role === "user") {
      return '<article id="chat-msg-' + id + '" class="chat-message-row user"><div class="chat-bubble user">' +
        htmlText(message.content || "") + attachmentHtml(message) + "</div></article>";
    }

    return '<article id="chat-msg-' + id + '" class="chat-message-row assistant">' +
      '<div class="chat-avatar">J</div><div class="chat-assistant-wrap">' +
      '<div class="chat-author">JARVIS ' +
      (status === "in_progress" ? '<span class="streaming-indicator">sta scrivendo…</span>' : "") +
      '</div><div class="chat-bubble assistant">' + htmlText(message.content || "") +
      "</div></div></article>";
  }

  function bindMessageActions() {
    document.querySelectorAll("[data-chat-approval]").forEach(function (button) {
      button.onclick = function () {
        answerApproval(
          button.getAttribute("data-chat-approval"),
          button.getAttribute("data-chat-decision")
        );
      };
    });

    document.querySelectorAll("[data-chat-answer-submit]").forEach(function (button) {
      button.onclick = function () {
        answerInputRequest(button.getAttribute("data-chat-answer-submit"));
      };
    });
  }

  function nearBottom() {
    const box = el("chat-messages");
    if (!box) return true;
    return box.scrollHeight - box.scrollTop - box.clientHeight < 180;
  }

  function scrollBottom(force) {
    const box = el("chat-messages");
    if (!box) return;
    if (force || nearBottom()) {
      requestAnimationFrame(function () { box.scrollTop = box.scrollHeight; });
    }
  }

  function renderMessages(messages, forceBottom) {
    chatState.messages = new Map((messages || []).map(function (message) {
      return [Number(message.id), message];
    }));
    const box = el("chat-messages");
    if (!box) return;
    const list = Array.from(chatState.messages.values()).sort(function (a, b) {
      return Number(a.id) - Number(b.id);
    });

    if (!list.length) {
      box.innerHTML =
        '<div class="chat-welcome"><div class="chat-orb">J</div><h3>Parla con JARVIS.</h3>' +
        "<p>Scrivi come in una chat normale. JARVIS sceglie gli agenti, lavora e ti mostra solo ciò che serve.</p></div>";
    } else {
      box.innerHTML = list.map(messageHtml).join("");
    }
    bindMessageActions();
    scrollBottom(Boolean(forceBottom));
  }

  function upsertMessage(message) {
    if (!message || !message.id) return;
    const shouldScroll = nearBottom();
    chatState.messages.set(Number(message.id), message);
    const existing = el("chat-msg-" + message.id);
    const html = messageHtml(message);
    if (existing) {
      existing.outerHTML = html;
    } else {
      const box = el("chat-messages");
      if (box) box.insertAdjacentHTML("beforeend", html);
    }
    bindMessageActions();
    if (shouldScroll) scrollBottom(true);
  }

  function setStatus(status) {
    chatState.status = status || "idle";
    const box = el("chat-status");
    if (!box) return;
    const labels = {
      idle: "PRONTO",
      working: "JARVIS STA LAVORANDO",
      waiting: "ATTENDE LA TUA RISPOSTA",
      error: "ERRORE"
    };
    const label = labels[chatState.status] || String(chatState.status).toUpperCase();
    box.className = "chat-status " + safe(chatState.status);
    box.innerHTML = '<span class="chat-status-dot"></span><span>' + safe(label) + "</span>";
    const stop = el("chat-stop");
    if (stop) stop.classList.toggle("hidden", chatState.status !== "working");
  }

  function renderRoute(thread) {
    const box = el("chat-route");
    if (!box) return;
    if (!thread) {
      box.innerHTML = "";
      return;
    }
    const collaborators = (thread.collaborators || []).map(agentDisplayName);
    box.innerHTML =
      "<span>" + safe(agentDisplayName(thread.primary_agent)) + "</span>" +
      (collaborators.length ? "<span>+ " + safe(collaborators.join(", ")) + "</span>" : "") +
      "<span>" + safe(thread.model || "") + "</span>";
  }

  function renderThreads(threads) {
    chatState.threads = threads || [];
    const box = el("chat-thread-list");
    if (!box) return;

    if (!chatState.threads.length) {
      box.innerHTML = '<div class="sub chat-sidebar-empty">Nessuna conversazione ancora.</div>';
      return;
    }

    box.innerHTML = chatState.threads.map(function (thread) {
      const active = chatState.thread === thread.thread_id ? " active" : "";
      return '<button class="chat-thread' + active + '" data-chat-thread="' + safe(thread.thread_id) + '">' +
        '<span class="chat-thread-title">' + safe(thread.title || "Conversazione") + "</span>" +
        '<span class="chat-thread-meta"><span class="chat-thread-dot ' + safe(thread.status || "idle") +
        '"></span>' + safe(agentDisplayName(thread.primary_agent)) + "</span></button>";
    }).join("");

    box.querySelectorAll("[data-chat-thread]").forEach(function (button) {
      button.onclick = function () { openChat(button.getAttribute("data-chat-thread")); };
    });
  }

  async function refreshThreads(selectLatest) {
    try {
      const response = await api("/api/chat/threads");
      renderThreads(response.threads || []);
      const note = el("chat-live-note");
      if (note) note.textContent = response.app_server && response.app_server.running
        ? "Codex App Server · connesso"
        : "Codex App Server · pronto";
      if (selectLatest && !chatState.thread && (response.threads || []).length) {
        await openChat(response.threads[0].thread_id);
      }
    } catch (error) {
      const note = el("chat-live-note");
      if (note) note.textContent = "Chat non disponibile";
      console.error(error);
    }
  }

  function stopStream() {
    if (chatState.abort) {
      chatState.abort.abort();
      chatState.abort = null;
    }
  }

  async function streamFetch(url, signal) {
    let response = await fetch(url, {headers: headers(false), signal: signal});
    if (response.status === 401) {
      const value = prompt("Token GE360 richiesto:");
      if (value !== null) localStorage.setItem("ge360_token", value.trim());
      response = await fetch(url, {headers: headers(false), signal: signal});
    }
    if (!response.ok) throw new Error("Stream chat: " + response.status);
    return response;
  }

  async function startStream(threadId) {
    stopStream();
    const controller = new AbortController();
    chatState.abort = controller;

    try {
      const response = await streamFetch(
        "/api/chat/threads/" + encodeURIComponent(threadId) + "/events",
        controller.signal
      );
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (chatState.thread === threadId && !controller.signal.aborted) {
        const part = await reader.read();
        if (part.done) break;
        buffer += decoder.decode(part.value, {stream: true});

        let split = buffer.indexOf("\n\n");
        while (split >= 0) {
          const block = buffer.slice(0, split);
          buffer = buffer.slice(split + 2);
          const data = block.split("\n").filter(function (line) {
            return line.indexOf("data:") === 0;
          }).map(function (line) {
            return line.slice(5).trim();
          }).join("\n");

          if (data) {
            try {
              const event = JSON.parse(data);
              if (event.type === "message.upsert") upsertMessage(event.message);
              if (event.type === "thread.status") setStatus(event.status);
              if (event.type === "turn.completed") {
                setStatus(event.status === "failed" ? "error" : "idle");
                refreshThreads(false);
              }
            } catch (error) {
              console.warn("Evento chat non valido", error);
            }
          }
          split = buffer.indexOf("\n\n");
        }
      }
    } catch (error) {
      if (!controller.signal.aborted && chatState.thread === threadId) {
        console.warn("Stream chat interrotto", error);
        setTimeout(function () {
          if (chatState.thread === threadId) startStream(threadId);
        }, 900);
      }
    }
  }

  async function openChat(threadId) {
    if (!threadId) return;
    stopStream();
    try {
      const response = await api("/api/chat/threads/" + encodeURIComponent(threadId));
      chatState.thread = threadId;
      el("chat-title").textContent = response.thread.title || "Conversazione";
      renderRoute(response.thread);
      setStatus(response.thread.status || "idle");
      renderMessages(response.messages || [], true);
      renderThreads(chatState.threads);
      startStream(threadId);
    } catch (error) {
      alert(error.message);
    }
  }

  function newChat() {
    stopStream();
    chatState.thread = null;
    chatState.messages = new Map();
    el("chat-title").textContent = "Nuova conversazione";
    renderRoute(null);
    setStatus("idle");
    renderMessages([], false);
    renderThreads(chatState.threads);
    el("chat-input").focus();
  }

  async function sendChat() {
    let text = el("chat-input").value.trim();
    const attachmentIds = Array.from(state.attachments);
    if (!text && attachmentIds.length) text = "Analizza gli allegati e dimmi cosa trovi.";
    if (!text) return;

    const button = el("chat-send");
    button.disabled = true;
    const original = button.textContent;
    button.textContent = "Invio…";

    try {
      if (!chatState.thread) {
        const response = await api("/api/chat/threads", {
          method: "POST",
          body: JSON.stringify({
            task: text,
            workspace_id: el("workspace").value,
            attachments: attachmentIds
          })
        });
        chatState.thread = response.thread.thread_id;
        el("chat-title").textContent = response.thread.title || "Conversazione";
        renderRoute(response.thread);
        chatState.messages = new Map();
        upsertMessage(response.user_message);
        setStatus("working");
        startStream(chatState.thread);
      } else {
        const response = await api(
          "/api/chat/threads/" + encodeURIComponent(chatState.thread) + "/messages",
          {
            method: "POST",
            body: JSON.stringify({text: text, attachments: attachmentIds})
          }
        );
        upsertMessage(response.message);
        setStatus("working");
      }

      el("chat-input").value = "";
      autoSizeInput();
      state.attachments.clear();
      renderAttachmentChips();
      document.querySelectorAll("[data-file-id]").forEach(function (checkbox) {
        checkbox.checked = false;
      });
      await refreshThreads(false);
      scrollBottom(true);
    } catch (error) {
      alert(error.message);
      setStatus("error");
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function interruptChat() {
    if (!chatState.thread) return;
    try {
      await api(
        "/api/chat/threads/" + encodeURIComponent(chatState.thread) + "/interrupt",
        {method: "POST"}
      );
    } catch (error) {
      alert(error.message);
    }
  }

  async function answerApproval(requestId, decision) {
    try {
      await api("/api/chat/requests/" + encodeURIComponent(requestId) + "/decision", {
        method: "POST",
        body: JSON.stringify({decision: decision})
      });
    } catch (error) {
      alert(error.message);
    }
  }

  async function answerInputRequest(requestId) {
    const inputs = Array.from(document.querySelectorAll("[data-chat-answer-request]")).filter(function (input) {
      return input.getAttribute("data-chat-answer-request") === requestId;
    });
    const answers = {};
    for (const input of inputs) {
      const value = input.value.trim();
      if (!value) {
        alert("Completa tutte le risposte richieste.");
        return;
      }
      answers[input.getAttribute("data-chat-answer-question")] = [value];
    }

    try {
      await api("/api/chat/requests/" + encodeURIComponent(requestId) + "/answer", {
        method: "POST",
        body: JSON.stringify({answers: answers})
      });
    } catch (error) {
      alert(error.message);
    }
  }

  function autoSizeInput() {
    const input = el("chat-input");
    if (!input) return;
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 180) + "px";
  }

  function init() {
    const required = ["chat-new", "chat-send", "chat-stop", "chat-attach", "chat-input"];
    if (required.some(function (id) { return !el(id); })) return;

    el("chat-new").onclick = newChat;
    el("chat-send").onclick = sendChat;
    el("chat-stop").onclick = interruptChat;
    el("chat-attach").onclick = function () { el("file-input").click(); };
    el("chat-input").addEventListener("input", autoSizeInput);
    el("chat-input").addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendChat();
      }
    });
    document.querySelectorAll("[data-chat-suggestion]").forEach(function (button) {
      button.onclick = function () {
        el("chat-input").value = button.getAttribute("data-chat-suggestion") || "";
        autoSizeInput();
        el("chat-input").focus();
      };
    });

    renderAttachmentChips();
    autoSizeInput();
    setTimeout(function () { refreshThreads(true); }, 250);
    setInterval(function () { refreshThreads(false); }, 5000);
  }

  init();
})();