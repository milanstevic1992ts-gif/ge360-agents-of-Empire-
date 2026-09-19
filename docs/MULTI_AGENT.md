# JARVIS multi-agent

JARVIS GE360 usa i subagenti personalizzati nativi di Codex.

Il thread principale `jarvis` è l'orchestratore. Gli otto profili iniziali sono `ge360_sysadmin`, `ge360_docker`, `ge360_developer`, `ge360_crm`, `ge360_data_intake`, `ge360_n8n_engineer`, `ge360_automation` e `ge360_wordpress_seo`.

`ge360_n8n_engineer` possiede il dominio tecnico n8n. `ge360_automation` resta il profilo trasversale per automazioni e integrazioni multi-app.

Le definizioni sorgente sono in `codex-agents/`; l'installer le copia in `~/.codex/agents/`.

## Memoria

L'installer abilita la memoria locale nativa di Codex. Codex conserva lo stato generato sotto `~/.codex/memories/`. Dentro Codex usa `/memories` per controllare lettura e generazione della memoria.

Le regole obbligatorie restano in `AGENTS.md`; la memoria è contesto storico. Non memorizzare intenzionalmente password, token o chiavi API.

## Aggiungere un agente

```bash
jarvis add-agent sicurezza "Controlla sicurezza Debian, Docker e servizi GE360"
```

Il nuovo file viene creato in `~/.codex/agents/sicurezza.toml`. Non serve modificare il core.

```bash
jarvis agents
```


## Data Intake Engineer

`ge360_data_intake` gestisce i file in ingresso prima che arrivino a CRM o automazioni:

- CSV / XLSX / JSON / TXT;
- riconoscimento colonne;
- schema GE360 canonico;
- normalizzazione;
- deduplica;
- report qualità;
- output derivato separato dall'originale.

Gli allegati caricati dalla dashboard sono persistenti in:

```text
~/.local/share/ge360-jarvis/inbox/
```

quindi non vengono cancellati da `jarvis update`.
