---
name: ge360-data-intake
description: Inspect, clean, normalize and deduplicate CSV/XLSX/JSON/TXT data before importing it into GE360 CRM, Mautic, Prospex or n8n.
---

# GE360 Data Intake

Always preserve the original uploaded file.

## Inspect first

Determine:
- file type;
- encoding;
- CSV delimiter/quote rules or Excel sheet names;
- headers;
- number of rows;
- empty columns;
- suspicious mixed data types;
- duplicate candidates.

Do not import before this inspection.

## Canonical contact schema

Prefer these canonical fields when relevant:

```text
tipo_contatto
nome
cognome
azienda
email
telefono
indirizzo
cap
citta
provincia
sito_web
categoria
fonte
data_verifica
stato_verifica
tags
note
campagna
opt_out
```

Not every dataset needs every field.

## Mapping

Map source headers to canonical fields explicitly.

Examples:

- `mail`, `e-mail`, `email_address` -> `email`
- `tel`, `telefono1`, `mobile`, `phone_number` -> `telefono`
- `studio`, `company`, `ragione_sociale` -> `azienda`

Never guess a semantic mapping when evidence is weak. Flag it for review.

## Deduplication

Use transparent tiers:

1. exact email;
2. exact normalized phone;
3. same normalized company + address;
4. probable duplicate: similar name/company plus another matching field.

Automatically merge only when confidence is high and no conflicting values exist.
Otherwise flag the pair for review.

## Validation

- email: syntax/shape checks, lowercase;
- phone: conservative normalization;
- website: normalize scheme/domain where safe;
- CAP/province/city: preserve source if uncertain;
- dates: convert only when unambiguous;
- booleans/opt-out: normalize explicit values only.

Never fabricate missing data.

## Output

Write a derived clean file, never overwrite the source.

Preferred outputs:
- CSV UTF-8 for broad interoperability;
- XLSX when multiple sheets or review tabs are helpful.

Produce a report:
- source rows;
- valid rows;
- corrected rows;
- exact duplicates;
- probable duplicates;
- rejected rows;
- missing critical fields;
- canonical field mapping;
- output path.

## CRM handoff

Before import, confirm destination field requirements with `ge360_crm`.
For automated import/sync, coordinate with `ge360_n8n_engineer`.

Do not hardcode CRM or n8n credentials into generated files or scripts.
