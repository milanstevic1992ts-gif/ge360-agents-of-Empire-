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
- modello + reasoning;
- Smart Router;
- playbook picker;
- team agenti;
- nuovo agente;
- log copiabile;
- uso Codex via /status;
- memoria operativa e feedback.

## Prossima fase: Codex App Server bridge

Non fare screen scraping per stabilire lo stato degli agenti.

Usare gradualmente `codex app-server` come fonte strutturata per:
- `model/list`: modelli disponibili realmente sull'account;
- `thread/status/changed`: idle / active / error;
- `turn/*`: stato del turno;
- `item/*`: tool call, messaggi, progress;
- subagent thread e handoff;
- token usage strutturato quando disponibile.

tmux resta il fallback e il terminale interattivo.

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
