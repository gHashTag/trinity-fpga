# GitHub collaboration backend — moved

The Spec Explorer's GitHub backend (OAuth sign-in, `/api/propose`, webhook)
lives in **[gHashTag/t27-github-collab](https://github.com/gHashTag/t27-github-collab)**.
Its README carries the setup steps, variables, endpoints and security notes.

This repository held a hand-copy of the service until 2026-10. It was removed
because Railway builds from t27-github-collab, so a fix merged here changed
nothing in production — the CORS allowlist (#804) had to be ported by hand.
Change the service there, not here.
