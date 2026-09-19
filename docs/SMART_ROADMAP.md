# GE360 JARVIS · Smart Roadmap

## Principio

JARVIS deve diventare più intelligente senza trasformarsi in uno stack pesante.
Codex resta il motore. GE360 aggiunge routing, memoria operativa, playbook,
osservabilità e controllo dei costi.

## Implementato

### Smart Router locale
- analizza il testo senza consumare crediti modello;
- sceglie agente principale e collaboratori;
- seleziona Luna / Terra / Sol;
- seleziona il reasoning effort;
- classifica il rischio;
- usa anche i feedback di incarichi simili.

### Memoria operativa
- SQLite locale in `runtime/jarvis-smart.sqlite3`;
- conserva solo metadati e anteprima redatta;
- non deve conservare password, token o API key;
- feedback riuscito / da migliorare;
- statistiche per agente.

### Playbook
Ricette riutilizzabili ispirate ai recipe system degli agent framework:
- SuiteCRM Health;
- Docker Recovery;
- systemd Recovery;
- n8n Workflow Check;
- WordPress Safe Change;
- Repo Bugfix.

### Dashboard
- chat JARVIS strutturata e streaming;
- cronologia conversazioni;
- card tool/approval;
- modello + reasoning;
- Smart Router;
- playbook picker;
- team agenti;
- nuovo agente;
- log copiabile;
- uso Codex via /status;
- memoria operativa e feedback.

## Codex App Server bridge · implementato in 0.7

La chat principale non usa screen scraping.

`codex app-server` resta persistente dietro il backend GE360 e comunica via stdio JSON-RPC. Il browser riceve eventi strutturati tramite SSE.

Usiamo già:
- `thread/start` / `thread/resume`;
- `thread/status/changed`;
- `turn/start` / `turn/steer` / `turn/interrupt`;
- `turn/completed`;
- `item/agentMessage/delta`;
- lifecycle `item/*` per tool, file change, MCP, web search e reasoning;
- approval request per comandi e modifiche file;
- request user input.

tmux resta il fallback e il terminale interattivo per power user.

Restano da integrare progressivamente:
- `model/list` come sorgente dinamica dei modelli;
- subagent thread/handoff più dettagliati;
- token usage strutturato quando disponibile.

## Dopo App Server

1. **Agent activity timeline**
   - JARVIS -> Docker -> CRM -> risultato;
   - durata per agente;
   - errori e retry.

2. **Dynamic model policy**
   - parte da Luna/low;
   - sale a Terra solo quando complessità/feedback lo richiede;
   - Sol solo per casi difficili o escalation;
   - possibilità di bloccare un budget massimo per sessione.

3. **Playbook learning**
   - suggerire automaticamente un playbook da incarichi riusciti;
   - mai salvare segreti;
   - richiedere approvazione prima di promuovere una nuova ricetta.

4. **Context packs**
   - piccoli file di contesto per SuiteCRM, Mautic, n8n, WordPress e repository;
   - caricati solo dall'agente che ne ha bisogno;
   - meno token rispetto a fornire tutto il contesto a tutti.

5. **MCP registry**
   - elenco centralizzato di MCP disponibili;
   - permessi per agente;
   - healthcheck MCP;
   - segreti fuori dalla repo.

6. **Session archive**
   - nome, task, route, modello, risultato e feedback;
   - ricerca per problema;
   - riapertura di una sessione storica.

## Regola architetturale

Prima di aggiungere una dipendenza always-on chiedere:
1. Codex lo fa già nativamente?
2. Si può fare con Python stdlib / SQLite?
3. Serve davvero un altro servizio?

Se la risposta alla terza domanda è no, non installarlo.
