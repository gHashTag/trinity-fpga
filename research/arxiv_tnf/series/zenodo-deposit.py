#!/usr/bin/env python3
"""Deposit the record version on Zenodo.

The metadata lives in zenodo-deposit.json and nowhere else, so a re-run cannot
disagree with the record that was minted.

The token is read from the macOS Keychain, service `zenodo-api`, so it crosses
no command line, no shell history and no process list. Store it once, typing it
into the prompt rather than into an argument:

    security add-generic-password -a "$USER" -s zenodo-api -T /usr/bin/security -U -w

Then:

    python3 zenodo-deposit.py check       # does the token authenticate at all
    python3 zenodo-deposit.py draft       # create, upload, describe
    python3 zenodo-deposit.py show ID     # read the draft back
    python3 zenodo-deposit.py publish ID

ZENODO_TOKEN in the environment overrides the Keychain, for CI.

The draft and publish steps are separate on purpose. Publishing mints a DOI and
cannot be undone: a published record can be superseded by a new version, never
withdrawn cleanly.

The token needs the scopes `deposit:write` and `deposit:actions`. Zenodo answers
403 "Permission denied." both for a token that lacks them and for a token that
does not exist, so a 403 here does not tell you which of the two you have.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://zenodo.org/api"
META = os.path.join(HERE, "zenodo-deposit.json")
PDF = os.path.join(HERE, "paper-c-record.pdf")
FILENAME = "ternary-network-floats-record-version.pdf"
KEYCHAIN_SERVICE = "zenodo-api"

_TOKEN = None


def token():
    """Read once, hold in memory, never print. Keychain first, env as override."""
    global _TOKEN
    if _TOKEN:
        return _TOKEN
    t = os.environ.get("ZENODO_TOKEN", "").strip()
    if not t:
        try:
            t = subprocess.run(
                ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                capture_output=True, text=True, check=True).stdout.strip()
        except subprocess.CalledProcessError:
            sys.exit("no token: store one with\n"
                     '  security add-generic-password -a "$USER" -s %s '
                     "-T /usr/bin/security -U -w" % KEYCHAIN_SERVICE)
    if not t:
        sys.exit("the keychain item %s is empty" % KEYCHAIN_SERVICE)
    _TOKEN = t
    return t


def call(method, url, data=None, ctype="application/json"):
    if not url.startswith("http"):
        url = API + url
    body = json.dumps(data).encode() if (data is not None and ctype == "application/json") else data
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", "Bearer " + token())
    if data is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def put_file(url, path):
    """Upload with curl, not urllib.

    urllib writes the whole body into one send and Zenodo drops the connection
    partway through a 31 MB PUT -- the failure surfaces as Errno 32 Broken pipe
    with no HTTP status to read. curl streams it and retries. The token goes in
    on stdin as a config file, never in argv, so it stays out of ps.
    """
    conf = 'header = "Authorization: Bearer %s"\n' % token()
    argv = ["curl", "-sS", "-K", "-", "--fail-with-body",
            "--retry", "3", "--retry-connrefused", "--retry-delay", "2",
            "--max-time", "1800", "--expect100-timeout", "30",
            "-X", "PUT", "--upload-file", path,
            "-w", "\n%{http_code}", url]
    r = subprocess.run(argv, input=conf, capture_output=True, text=True)
    out = r.stdout.rsplit("\n", 1)
    body, code = (out[0], out[1]) if len(out) == 2 else (r.stdout, "000")
    if r.returncode != 0 and code == "000":
        sys.exit("curl failed (%d): %s" % (r.returncode, r.stderr[:400]))
    return int(code), body.encode()


def parse(status, payload, what):
    try:
        j = json.loads(payload)
    except Exception:
        sys.exit("%s: HTTP %d, unparseable body: %s" % (what, status, payload[:400]))
    if status >= 400:
        print(json.dumps(j, indent=2, ensure_ascii=False)[:2000])
        sys.exit("%s failed: HTTP %d" % (what, status))
    return j


def check():
    """Does the token authenticate, before anything is created."""
    t = token()
    print("token: %d chars, ends %s, source: %s"
          % (len(t), t[-3:], "env" if os.environ.get("ZENODO_TOKEN") else "keychain"))
    status, payload = call("GET", "/deposit/depositions?size=3")
    if status == 403:
        sys.exit("HTTP 403 Permission denied.\n"
                 "Zenodo answers this both for a token that does not exist and for one\n"
                 "without deposit:write -- it does not say which. Re-issue at\n"
                 "https://zenodo.org/account/settings/applications/tokens/new/\n"
                 "with deposit:write AND deposit:actions ticked.")
    j = parse(status, payload, what="check")
    print("HTTP", status, "| the token authenticates | existing depositions:", len(j))
    for d in j:
        print("  ", d.get("id"), d.get("state"), (d.get("title") or "(untitled)")[:60])


def draft(dep_id=None):
    if dep_id is None:
        dep = parse(*call("POST", "/deposit/depositions", {}), what="create")
        dep_id = dep["id"]
        print("draft", dep_id, "created")
    upload(dep_id)
    describe(dep_id)


def upload(dep_id):
    size = os.path.getsize(PDF)
    dep = parse(*call("GET", "/deposit/depositions/%s" % dep_id), what="read")
    bucket = dep["links"]["bucket"]
    print("uploading %.1f MB into draft %s ..." % (size / 1e6, dep_id))
    up = parse(*put_file(bucket + "/" + FILENAME, PDF), what="upload")
    print("stored", up.get("key"), up.get("size"), "bytes (local", size, "bytes)")
    if up.get("size") != size:
        sys.exit("size mismatch: the server did not store what was sent")


def describe(dep_id):
    meta = json.load(open(META))
    out = parse(*call("PUT", "/deposit/depositions/%s" % dep_id, meta), what="metadata")
    m = out.get("metadata", {})
    print("title:  ", m.get("title"))
    print("license:", m.get("license"), "| date:", m.get("publication_date"))
    print("reserved DOI:", m.get("prereserve_doi", {}).get("doi"))
    print("\nreview it, then:  ZENODO_TOKEN=... python3 zenodo-deposit.py publish %s" % dep_id)


def show(dep_id):
    j = parse(*call("GET", "/deposit/depositions/" + dep_id), what="read")
    print(json.dumps({k: j.get(k) for k in ("id", "state", "submitted", "title", "doi")},
                     indent=2, ensure_ascii=False))
    for f in j.get("files", []):
        print("  file:", f.get("filename"), f.get("filesize"), f.get("checksum"))


def publish(dep_id):
    j = parse(*call("POST", "/deposit/depositions/%s/actions/publish" % dep_id), what="publish")
    print("PUBLISHED")
    print("  DOI:   ", j.get("doi"))
    print("  URL:   ", j.get("doi_url") or j.get("links", {}).get("record_html"))
    print("  record:", j.get("record_id"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "draft":
        draft(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "upload":
        upload(sys.argv[2])
    elif cmd == "meta":
        describe(sys.argv[2])
    elif cmd == "show":
        show(sys.argv[2])
    elif cmd == "publish":
        publish(sys.argv[2])
    else:
        sys.exit(__doc__)
