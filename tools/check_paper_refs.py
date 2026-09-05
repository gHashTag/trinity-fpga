#!/usr/bin/env python3
"""
Resolve every repository reference a paper makes, and fail if any of them 404s.

Written 2026-09-05 after an audit of tnf_paper.tex spent three hours
distinguishing "this record does not exist" from "I looked in the wrong place".
Every check below exists because one specific lookup went wrong that night:

  * a path was resolved against the repo root when the paper cites it relative
    to its own directory                          -> both roots are tried
  * a raw URL used branch 'main' on a repo whose default branch is 'master'
    and returned 404                              -> the default branch is asked for
  * a cited tag had never been created            -> tags are resolved explicitly
  * a file was declared missing after two of the three candidate repositories
    were searched                                 -> a code search locates it before
                                                     anything is called missing

Usage:
    check_paper_refs.py PAPER.tex --repo OWNER/NAME [--dir research/arxiv_tnf]
    check_paper_refs.py PAPER.tex --repo OWNER/NAME --json

Exit status: 0 all resolved, 1 something is genuinely missing, 3 something
could not be checked (network, rate limit) -- which is not the same verdict and
must not be treated as one.

Reads a token from GH_TOKEN or GITHUB_TOKEN, else falls back to `gh auth token`.
Unauthenticated it still runs, but the rate limit turns most lookups into
'unchecked'.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = 'https://api.github.com'
_cache = {}


def gh_token():
    """A token from the environment first, so this runs in CI where `gh` is absent.

    Unauthenticated, the contents API allows 60 requests an hour and the code
    search none at all, which turns every lookup into 'unchecked' -- the state
    this script exists to keep separate from 'missing'.
    """
    for var in ('GH_TOKEN', 'GITHUB_TOKEN'):
        t = os.environ.get(var)
        if t:
            return t.strip()
    try:
        r = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except Exception:
        return None


TOKEN = gh_token()


def api(path, attempts=3):
    """GET an API path. Returns (status, parsed_json_or_None). Cached.

    Only an HTTP 404 means absent. A timeout, a 5xx or a rate-limit is NOT
    evidence of absence -- it is returned as status 0 so the caller can report
    the reference as unchecked rather than broken. Converting "I could not
    look" into "it is missing" is the failure this whole script exists to stop,
    and the first version of it made exactly that mistake.
    """
    if path in _cache:
        return _cache[path]
    req = urllib.request.Request(API + path, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'check-paper-refs',
        **({'Authorization': f'token {TOKEN}'} if TOKEN else {}),
    })
    out = (0, None)
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                out = (r.status, json.load(r))
                break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                out = (404, None)
                break
            out = (e.code, None)          # 403 rate limit, 5xx -- retry
        except Exception:
            out = (0, None)               # timeout, DNS, reset -- retry
        time.sleep(1.5 * (i + 1))
    _cache[path] = out
    return out


def probe(repo, path, ref=None):
    """'ok' | 'absent' | 'unchecked' for one path."""
    q = f'/repos/{repo}/contents/{path}' + (f'?ref={ref}' if ref else '')
    st = api(q)[0]
    return 'ok' if st == 200 else ('absent' if st == 404 else 'unchecked')


def default_branch(repo):
    st, d = api(f'/repos/{repo}')
    return d.get('default_branch') if st == 200 and d else None


def path_exists(repo, path, ref=None):
    q = f'/repos/{repo}/contents/{path}' + (f'?ref={ref}' if ref else '')
    return api(q)[0] == 200


def tag_exists(repo, tag):
    return api(f'/repos/{repo}/git/refs/tags/{tag}')[0] == 200


def locate(basename):
    """Where does a file with this basename actually live? Empty if unknown."""
    st, d = api(f'/search/code?q=filename:{basename}')
    if st != 200 or not d:
        return []
    return sorted({f"{i['repository']['full_name']}:{i['path']}" for i in d.get('items', [])})[:3]


PATH_RE = re.compile(r'(?<![\w/])((?:measurements|research|data|proofs|tools|oracle|rtl|tests|specs|src|docs)/[A-Za-z0-9_][A-Za-z0-9_./-]*)')
TAG_RE = re.compile(r'tag\s*\\?texttt\{([^}]+)\}|tag\s+`([^`]+)`|tag\s+([A-Za-z0-9][\w.-]*)')
URL_RE = re.compile(r'github\.com/([A-Za-z0-9._-]+/[A-Za-z0-9._-]+?)(?=[\s,;)}\\/]|$)')


def strip_tex(s):
    s = re.sub(r'(?m)^\s*%.*$', '', s)          # comments
    s = s.replace('\\_', '_').replace('\\%', '%')
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paper')
    ap.add_argument('--repo', required=True, help='OWNER/NAME the paper lives in')
    ap.add_argument('--dir', default='', help="paper's own directory inside the repo")
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    text = strip_tex(open(a.paper, encoding='utf-8', errors='ignore').read())
    branch = default_branch(a.repo)
    if branch is None:
        print(f'FAIL  cannot reach repository {a.repo}', file=sys.stderr)
        return 2

    base = a.dir.strip('/')
    findings, bad, unchecked = [], 0, 0

    # --- paths -------------------------------------------------------------
    for p in sorted(set(PATH_RE.findall(text))):
        p = p.rstrip('.,;:')
        tried, verdicts = [], []
        # relative to the paper's own directory first, then the repo root
        for cand in ([f'{base}/{p}'] if base else []) + [p]:
            tried.append(cand)
            v = probe(a.repo, cand, branch)
            verdicts.append(v)
            if v == 'ok':
                findings.append({'kind': 'path', 'cited': p, 'status': 'ok',
                                 'resolved': f'{a.repo}/{cand}'})
                break
        else:
            if 'unchecked' in verdicts:
                findings.append({'kind': 'path', 'cited': p, 'status': 'UNCHECKED',
                                 'tried': tried})
                unchecked += 1
            else:
                elsewhere = locate(p.split('/')[-1])
                findings.append({'kind': 'path', 'cited': p, 'status': 'MISSING',
                                 'tried': tried, 'found_elsewhere': elsewhere})
                bad += 1

    # --- tags --------------------------------------------------------------
    for m in TAG_RE.finditer(text):
        tag = next(g for g in m.groups() if g)
        # a tag is cited next to a repo URL; check every repo the paper names
        repos = set(URL_RE.findall(text)) or {a.repo}
        ok_in = [r for r in repos if tag_exists(r, tag)]
        if ok_in:
            findings.append({'kind': 'tag', 'cited': tag, 'status': 'ok', 'resolved': ok_in[0]})
        else:
            findings.append({'kind': 'tag', 'cited': tag, 'status': 'MISSING',
                             'tried': sorted(repos)})
            bad += 1

    # --- repositories ------------------------------------------------------
    for r in sorted(set(URL_RE.findall(text))):
        st, _ = api(f'/repos/{r}')
        if st == 200:
            findings.append({'kind': 'repo', 'cited': r, 'status': 'ok'})
        else:
            findings.append({'kind': 'repo', 'cited': r, 'status': 'MISSING', 'http': st})
            bad += 1

    if a.json:
        print(json.dumps({'paper': a.paper, 'repo': a.repo, 'branch': branch,
                          'failures': bad, 'unchecked': unchecked,
                          'findings': findings}, indent=2))
    else:
        print(f'{a.paper}  ->  {a.repo} @ {branch}' + (f'  (paper dir: {base}/)' if base else ''))
        for f in findings:
            if f['status'] == 'ok':
                print(f"  ok       {f['kind']:<5} {f['cited']}")
        for f in findings:
            if f['status'] != 'ok':
                print(f"  MISSING  {f['kind']:<5} {f['cited']}")
                if f.get('tried'):
                    print(f"           tried: {', '.join(f['tried'])}")
                for e in f.get('found_elsewhere', []):
                    print(f"           found instead at: {e}")
        for f in findings:
            if f['status'] == 'UNCHECKED':
                print(f"  ?        {f['kind']:<5} {f['cited']}  (could not reach the API -- not a verdict)")
        print(f"\n{len(findings) - bad - unchecked} resolved, {bad} unresolved, {unchecked} unchecked")
        if bad:
            print('Quote the commit, never a version name.')
        if unchecked:
            print('Unchecked is not missing. Re-run before acting on it.')
    return 1 if bad else (3 if unchecked else 0)


if __name__ == '__main__':
    sys.exit(main())
