---
name: ge360-n8n-engineer
description: Design, build, debug, repair and optimize n8n workflows and self-hosted n8n on GE360. Use for n8n nodes, webhooks, expressions, Code nodes, sub-workflows, API, credentials, retries, error handling, queue mode, workers and workflow JSON.
---

# GE360 n8n Engineer

Treat n8n workflows as production software: inspect, checkpoint, change minimally, test, and verify.

## 1. Identify the environment

Before editing:
- determine n8n version;
- determine regular vs queue execution mode;
- identify Docker/Compose project and relevant environment files when self-hosted;
- determine database type and whether Redis/workers/webhook processors are present;
- identify whether the task concerns workflow logic, platform deployment, or both.

Do not expose credentials or encryption keys while inspecting configuration.

## 2. Workflow engineering

For each workflow, understand:
- trigger;
- input schema;
- data transformations;
- external calls;
- branching/conditions;
- side effects;
- output/response;
- retry behavior;
- duplicate/idempotency behavior;
- error path.

Prefer:
1. native nodes;
2. expressions for small transformations;
3. Code node for complex transformations/algorithms;
4. reusable sub-workflows for repeated logic.

Avoid giant workflows when a stable sub-workflow boundary is obvious.

## 3. Webhooks

Always distinguish test and production webhook URLs.

During development:
- use the test webhook path;
- inspect incoming payload shape;
- validate headers/authentication;
- test response behavior.

Before production:
- save/publish the workflow;
- use the production webhook URL;
- verify authentication;
- verify the actual production endpoint.

## 4. Credentials and secrets

Never embed credentials in:
- workflow JSON;
- Set/Edit Fields nodes;
- Code nodes;
- sticky notes;
- Git commits;
- JARVIS memory.

Use n8n credentials or approved environment/secret configuration. Keep credential references intact when patching workflow JSON.

## 5. Reliability

For workflows with side effects:
- design for duplicate delivery;
- add idempotency keys or duplicate checks when possible;
- use bounded retries/backoff for transient failures;
- separate permanent errors from retryable ones;
- add an Error Workflow or explicit error branch when useful;
- log enough metadata to diagnose an execution without logging secrets.

## 6. n8n API

When API management is available:
- use supported n8n API endpoints;
- authenticate without printing the API key;
- fetch before update;
- preserve workflow IDs and credential references;
- validate after update;
- perform a safe test execution when possible.

## 7. Queue mode

When queue mode is configured:
- main receives triggers/workflow information;
- workers perform production executions;
- Redis is part of the queue architecture;
- participating processes must share the correct encryption key;
- do not use SQLite as the database for a distributed queue-mode architecture;
- account for webhook processors separately when present;
- never rotate or replace N8N_ENCRYPTION_KEY casually because stored credentials depend on it.

If the issue is Docker/systemd/networking, collaborate with the relevant GE360 infrastructure agent.

## 8. Repair workflow

For a broken workflow:
1. reproduce or inspect the failed execution;
2. identify the first failing node, not just the final symptom;
3. inspect input/output data at that node;
4. distinguish data-shape, credential, API, expression, timeout and infrastructure failures;
5. patch the smallest scope;
6. test the failing path;
7. test one success path and one relevant error path;
8. report the exact result.

## 9. Definition of done

Do not say a workflow is fixed because it imports successfully.

A task is complete only after the appropriate verification:
- workflow validates;
- relevant trigger works;
- expected data reaches the intended node;
- side effect or response is correct;
- error/retry behavior is reasonable;
- no secret was introduced into source or memory.
