# GE360 Agent Control Center

Un super-terminale leggero per Debian che usa **OpenAI Codex CLI** come agente operativo e aggiunge:

- sessioni persistenti con `tmux`;
- dashboard Web/mobile;
- stato di sistema, Docker e servizi systemd;
- skill GE360 per diagnosi, recovery, deploy e backup;
- regole di sicurezza per evitare operazioni distruttive automatiche;
- autenticazione Codex riutilizzata dall'utente Linux che esegue il servizio;\n- 6 subagenti Codex specializzati e memoria locale;\n- selezione modello Codex dalla dashboard (Luna/Terra/Sol);\n- pannello consumo basato sull'output reale di `/status`;\n- log live copiabile e creazione di nuovi agenti dalla UI.

## Filosofia

Un solo orchestratore. Codex resta il cervello; GE360 aggiunge controllo, memoria operativa, skill e una UI semplice.

```text
Browser / telefono
       |
       v
GE360 Agent Control Center
       |
       +--> tmux --> Codex CLI --> Debian / Docker / Git
       |
       +--> health API --> systemd / Docker / /proc
```

## Sicurezza

Il progetto **non** abilita sudo globale senza password e **non** auto-approva comandi distruttivi.

Le istruzioni GE360 impongono:

1. diagnosi prima della modifica;
2. backup prima di cambiare configurazioni o dati;
3. Git diff/commit quando disponibile;
4. divieto di `docker volume rm`, `docker system prune`, DROP/TRUNCATE e cancellazioni massive senza conferma esplicita;
5. verifica finale dopo ogni correzione.

La dashboard deve restare privata: di default ascolta solo su `127.0.0.1`. Per accesso remoto usare Tailscale/reverse proxy privato.

## Installazione rapida

```bash
git clone https://github.com/milanstevic1992ts-gif/ge360-agents-of-Empire-.git
cd ge360-agents-of-Empire-
bash scripts/install.sh
```

Poi:

```bash
jarvis
```

oppure apri la dashboard locale:

```text
http://127.0.0.1:8789
```

Per controllare il login Codex:

```bash
codex login status
```

Per effettuare il login:

```bash
codex
```

e scegli **Sign in with ChatGPT**.

## Componenti

- `ge360_agent/` backend Python/FastAPI leggero;
- `web/` dashboard responsive senza framework;
- `.agents/skills/` skill native Codex;
- `AGENTS.md` regole operative GE360;
- `scripts/` installazione, login, doctor;
- `systemd/` servizio Debian.

## Ispirazione

Architettura studiata su:

- Agent Deck — gestione sessioni/agenti e sandbox;
- Agent of Empires — TUI/Web/mobile e sessioni persistenti;
- AgentBox — separazione runtime e riuso dell'autenticazione Codex;
- DevOps AI Skill Pack — modello concettuale per skill DevOps.

Il codice di questa repository è un'implementazione GE360 nuova e minimale; non incorpora automaticamente i repository esterni.

Vedi `THIRD_PARTY_NOTICES.md`.

## Stato

### Fase 1 — base operativa
- [x] struttura repository
- [x] backend health
- [x] session manager tmux
- [x] avvio Codex
- [x] dashboard Web/mobile
- [x] skill GE360
- [x] installer Debian
- [x] systemd

### Fase 2
- [ ] streaming terminale WebSocket
- [ ] notifiche stato agente
- [ ] profili per Mautic / n8n / SuiteCRM / Prospex
- [ ] backup automatici per stack configurati
- [ ] audit log strutturato

### Fase 3
- [ ] PWA
- [ ] integrazione Tailscale guidata
- [ ] MCP GE360
- [ ] recovery playbook automatici con approvazione

## Licenza

MIT. Vedi `LICENSE`.
