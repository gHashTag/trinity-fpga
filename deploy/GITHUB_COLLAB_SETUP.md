# GitHub collaboration backend — setup

Lets a visitor connect their GitHub account from `t27.ai/#/specs`, edit a spec
in the browser, and have it land as a pull request **authored by them**.

Three things have to be created by hand, because they need your GitHub account
and your Railway project. Everything else is in the repo.

---

## 1. Register the OAuth App

<https://github.com/settings/developers> → **OAuth Apps** → **New OAuth App**

| Field | Value |
|---|---|
| Application name | `t27 Spec Explorer` |
| Homepage URL | `https://t27.ai` |
| Authorization callback URL | `https://<railway-service>.up.railway.app/auth/callback` |

The callback URL must match `PUBLIC_ORIGIN` exactly, path included — GitHub
compares it literally and rejects the exchange on any difference. Deploy first
if you do not know the Railway hostname yet, then come back and fill it in.

Press **Generate a new client secret** and keep the page open; GitHub shows the
secret once.

> **OAuth App, not GitHub App.** A GitHub App authenticates by signing an RS256
> JWT. Zig 0.16's `std.crypto` has `Certificate.rsa.PublicKey` but no
> `SecretKey` — it verifies RSA and cannot sign it, so there is no signer in std
> to call, and `.claude/rules/no-shell-scripts.md` rules out shelling to
> openssl. The practical difference is whose name is on the PR: an App opens
> them as a bot, this opens them as the contributor — which is the better
> attribution for a spec contribution anyway, and their own permissions bound
> what the token can do.

---

## 2. Deploy the service

```bash
railway add --service t27-github-collab
railway up --detach
```

Build config lives in `deploy/railway.github-collab.toml`
(Dockerfile: `deploy/Dockerfile.github-collab`).

Then generate a public domain for the service and use it as `PUBLIC_ORIGIN`.

---

## 3. Set the variables

In the Railway dashboard for the service — **not in this repo, and not in any
file that gets committed**:

| Variable | Value |
|---|---|
| `GITHUB_CLIENT_ID` | from step 1 |
| `GITHUB_CLIENT_SECRET` | from step 1 — secret |
| `GITHUB_WEBHOOK_SECRET` | 32 random bytes — secret (see below) |
| `PUBLIC_ORIGIN` | `https://<railway-service>.up.railway.app` |
| `ALLOWED_ORIGIN` | `https://t27.ai` |

`PORT` is injected by Railway.

Generate a webhook secret with:

```bash
openssl rand -hex 32
```

The service **exits at boot** if any required variable is missing. That is
deliberate: a process that starts and then fails every request looks healthy to
the restart policy and stays broken quietly.

---

## 4. Point the webhook at it

Repo → **Settings → Webhooks → Add webhook**

| Field | Value |
|---|---|
| Payload URL | `https://<railway-service>.up.railway.app/webhook` |
| Content type | `application/json` |
| Secret | the same `GITHUB_WEBHOOK_SECRET` |
| Events | Pull requests, Issues (or whichever you want) |

---

## Verifying it works

```bash
curl -s https://<service>.up.railway.app/health
```

```json
{"status":"ok","service":"github-collab"}
```

An unsigned or wrongly-signed webhook must come back `401`. Locally that was
checked against a real HMAC produced by `openssl dgst -sha256 -hmac`, which is
the same construction GitHub uses:

```
unsigned       -> 401
bad signature  -> 401
good signature -> 200
```

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness, no auth |
| GET | `/auth/github` | redirect into GitHub consent |
| GET | `/auth/callback` | exchange `?code` for a token |
| POST | `/api/propose` | branch + commit + PR, as the connected user |
| POST | `/webhook` | GitHub events, HMAC-verified |

## Security notes

- **Scope is `public_repo`, not `repo`.** `repo` would grant write access to
  every private repository a visitor owns, to do a job that never touches one.
  There is a test asserting `scope=repo` never appears in the authorize URL.
- **The access token is set as an `HttpOnly; Secure; SameSite=Lax` cookie**, never
  put in a redirect URL — query strings end up in browser history, server logs
  and `Referer` headers.
- **CSRF `state` is compared in constant time**, as is the webhook HMAC. A plain
  `mem.eql` leaks how many leading bytes matched, which is enough to forge a
  value byte by byte.
- **CORS is scoped to `ALLOWED_ORIGIN`, never `*`**, because these requests
  carry a credentialed cookie.
- The token is held only in the visitor's cookie. The service stores nothing.
