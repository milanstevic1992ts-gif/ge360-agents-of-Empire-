# GE360 Agent Control Center

Un super-terminale leggero per Debian che usa **OpenAI Codex CLI** come motore e aggiunge un livello GE360 per controllo, routing, memoria operativa e dashboard.

## Cosa fa oggi

- sessioni persistenti con `tmux`;
- dashboard Web/mobile privata;
- stato Debian, Docker e servizi systemd;
- login Codex riutilizzato dall'utente Linux;
- **JARVIS + 6 subagenti Codex specializzati**;
- creazione semplice di un 7°, 8° o ulteriore agente;
- selezione modello **GPT-5.6 Luna / Terra / Sol**;
- selezione del **reasoning effort**;
- pannello uso/quota basato sull'output reale di `/status`;
- log terminale live e copiabile;
- **Smart Router locale** che non usa crediti modello per decidere come instradare il lavoro;
- playbook riutilizzabili;
- memoria operativa SQLite con feedback;
- apprendimento leggero dai risultati di incarichi simili;
- regole di sicurezza per evitare operazioni distruttive automatiche.

## Architettura

```text
Browser / telefono
       |
       v
GE360 JARVIS Dashboard
       |
       +--> Smart Router
       |      +--> agente principale
       |      +--> collaboratori
       |      +--> modello
       |      +--> reasoning
       |      +--> rischio
       |
       +--> tmux --> Codex CLI --> Debian / Docker / Git
       |
       +--> 6+ subagenti Codex
       |
       +--> memoria operativa SQLite
       |
       +--> health API --> systemd / Docker / /proc
```

Codex resta il cervello. GE360 aggiunge l'orchestrazione senza installare un secondo framework multi-agente pesante.

## Team iniziale

- `ge360_sysadmin` — Debian, systemd, rete, pacchetti, permessi;
- `ge360_docker` — Docker/Compose, container, healthcheck, volumi;
- `ge360_developer` — codice, bugfix, Git, test, API;
- `ge360_crm` — SuiteCRM, Mautic, Prospex;
- `ge360_automation` — n8n, webhook, workflow e integrazioni;
- `ge360_wordpress_seo` — WordPress, plugin, performance e SEO locale.

Aggiungere un nuovo agente:

```bash
jarvis add-agent sicurezza "Specialista sicurezza Debian, Docker e servizi GE360"
```

## Smart Router

Dalla dashboard descrivi il lavoro in linguaggio naturale. Il router calcola localmente:

1. agente principale;
2. eventuali collaboratori;
3. Luna / Terra / Sol;
4. reasoning effort;
5. livello di rischio.

Poi **Avvia Smart** crea la sessione Codex e passa a JARVIS un incarico strutturato.

Il routing usa regole trasparenti e anche un piccolo bonus/malus derivato dai feedback di incarichi simili già eseguiti.

## Memoria operativa

La memoria GE360 è separata dalla memoria nativa Codex.

File runtime:

```text
runtime/jarvis-smart.sqlite3
```

Conserva:

- sessione;
- anteprima ridotta dell'incarico;
- agente scelto;
- collaboratori;
- modello;
- rischio;
- feedback riuscito / da migliorare.

I pattern comuni di password, token e API key vengono redatti prima del salvataggio.

Le regole obbligatorie restano in `AGENTS.md`: la memoria non sostituisce la policy.

## Playbook

Sono presenti ricette riutilizzabili in `recipes/`:

- SuiteCRM Health;
- Docker Recovery;
- systemd Recovery;
- n8n Workflow Check;
- WordPress Safe Change;
- Repo Bugfix.

Il sistema è volutamente semplice: file TOML leggibili e versionabili.

## Controllo consumo

La dashboard permette di scegliere modello e reasoning.

Indicazione generale:

- **Luna + Low**: diagnostica e lavori semplici;
- **Terra + Medium**: lavori multi-step e multi-dominio;
- **Sol + High**: casi difficili, architettura, debugging complesso.

Il saldo completo dell'account non viene inventato. Il pannello consumo mostra solo ciò che Codex espone realmente tramite `/status`.

## Sicurezza

Il progetto **non** abilita sudo globale senza password e **non** auto-approva operazioni distruttive.

Le istruzioni GE360 impongono:

1. diagnosi prima della modifica;
2. backup prima di cambiare configurazioni o dati;
3. Git status/diff quando disponibile;
4. niente `docker volume rm`, `docker system prune`, DROP/TRUNCATE o cancellazioni massive automatiche;
5. verifica finale dopo ogni correzione;
6. niente password/token/API key nella repo o nella memoria operativa.

La dashboard ascolta di default solo su `127.0.0.1`. Per accesso remoto usare Tailscale o un reverse proxy privato.

## Installazione

```bash
git clone https://github.com/milanstevic1992ts-gif/ge360-agents-of-Empire-.git
cd ge360-agents-of-Empire-
bash scripts/install.sh
```

Comandi principali:

```bash
jarvis
jarvis agents
jarvis memories
jarvis doctor
jarvis update
```

Dashboard:

```text
http://127.0.0.1:8789
```

## Doctor

`jarvis doctor` controlla:

- Python, tmux, Git, curl;
- Docker;
- Codex e login;
- import backend + Smart Router;
- unit test;
- subagenti installati;
- playbook;
- sintassi JavaScript quando Node è disponibile;
- servizio systemd;
- API dashboard.

## Prossima evoluzione

La prossima fase importante è un bridge verso **Codex App Server** per usare eventi strutturati invece di dedurre lo stato dal terminale:

- elenco modelli realmente disponibili;
- `thread/status/changed`;
- `turn/*`;
- `item/*`;
- stati subagenti;
- timeline di handoff;
- usage strutturato quando disponibile.

tmux resterà il fallback interattivo.

Vedi:

- `docs/MULTI_AGENT.md`
- `docs/SMART_ROADMAP.md`

## Ispirazione

Sono state studiate idee da:

- OpenAI Codex — subagenti, memoria, skill, App Server;
- Agent of Empires — dashboard agent-aware e session management;
- Letta — memoria persistente e apprendimento dall'esperienza;
- Goose — recipe/playbook ed estensioni;
- LangGraph — handoff espliciti;
- CrewAI — osservabilità e feedback.

GE360 resta un'implementazione nuova e minimale: non incorpora questi framework come dipendenze runtime.

## Licenza

MIT. Vedi `LICENSE`.
