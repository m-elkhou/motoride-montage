# Security and privacy

## What is never committed

The `.gitignore` is deliberately strict. It excludes, by category:

| Category | Examples |
|---|---|
| **Secrets** | `.env*`, `secrets/`, `client_secret*.json`, `token*.json`, `*.pem`, `*.key`, `credentials*.json`, `auth.log`, `auth.err`, `local_paths.json` |
| **Data and state** | `data/`, `out/`, `props/`, `vo/`, `meta/`, `specs/`, `manifest.json`, `scan/*.json` (including `scan/gen_config.json`), `scan/*.jsonl`, `scan/mont/`, the upload ledger `meta/_uploaded.json`, databases, caches |
| **Media** | all video, audio and image formats, and the whole `public/` folder (your footage, your music) |
| **Logs and backups** | `*.log`, `*.err`, `*.bak*`, temp files |
| **Tooling** | `node_modules/`, `__pycache__/`, virtualenvs, IDE and assistant session folders, the generated `site/` |

Before the first public push the working tree was checked for credentials, tokens, e-mail addresses and
private identifiers, and the git history contains only the original Remotion template commit.

## Why the OAuth log is excluded

The Google consent flow prints an authorisation URL containing the OAuth **client id**, a `state` value and a
PKCE `code_challenge`, and the local redirect receives the authorisation **code**. These must never be shared
or committed, so any `auth.log` / `auth.err` is ignored.

## Handling credentials

- The YouTube OAuth client and token belong to **social2shorts** (`secrets/`), not to this repository.
- If a token is ever exposed, **revoke it** in your Google account's security page and delete `token.json`;
  the next `social2shorts auth` run issues a new one.
- Never paste verification codes, passwords or consent URLs into logs, issues or documentation.

## Privacy of footage

Raw clips can contain faces, number plates and locations. They stay local. The planner excludes
footage dates you mark as personal (`EXCL_DATE` in `scan/gen_batch.py`): review that list before sharing
any generated output.

## Reporting a problem

Open a GitHub issue **without** secrets or personal data. If a credential was committed by mistake, rotate
it first, then rewrite history.

## Anonymity

The privacy gate ([details](pipeline/privacy.md)) keeps faces and bystanders out of the videos. Everything it
produces stays local and git-ignored: `PRIVATE/` (quarantine), `models/`, `scan/privacy_pool.json`,
`scan/privacy_blocklist.json`, `meta/_privacy*` and `out/_cat/`. The documentation never names the channel or its
social accounts.
