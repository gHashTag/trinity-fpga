#!/usr/bin/env python3
"""Deposit the record version on Zenodo.

The metadata lives in zenodo-deposit.json and nowhere else, so a re-run cannot
disagree with the record that was minted. The token is read from the environment
and is never written to a file, printed, or committed:

    ZENODO_TOKEN=... python3 zenodo-deposit.py draft     # create, upload, describe
    ZENODO_TOKEN=... python3 zenodo-deposit.py show ID   # read the draft back
    ZENODO_TOKEN=... python3 zenodo-deposit.py publish ID

The draft and publish steps are separate on purpose. Publishing mints a DOI and
cannot be undone: a published record can be superseded by a new version, never
withdrawn cleanly.

The token needs the scopes `deposit:write` and `deposit:actions`. Zenodo answers
403 "Permission denied." both for a token that lacks them and for a token that
does not exist, so a 403 here does not tell you which of the two you have.
"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://zenodo.org/api"
META = os.path.join(HERE, "zenodo-deposit.json")
PDF = os.path.join(HERE, "paper-c-record.pdf")
FILENAME = "ternary-network-floats-record-version.pdf"


def token():
    t = os.environ.get("ZENODO_TOKEN")
    if not t:
        sys.exit("set ZENODO_TOKEN (scopes: deposit:write, deposit:actions)")
    return t.strip()


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


def parse(status, payload, what):
    try:
        j = json.loads(payload)
    except Exception:
        sys.exit("%s: HTTP %d, unparseable body: %s" % (what, status, payload[:400]))
    if status >= 400:
        print(json.dumps(j, indent=2, ensure_ascii=False)[:2000])
        sys.exit("%s failed: HTTP %d" % (what, status))
    return j


def draft():
    meta = json.load(open(META))
    size = os.path.getsize(PDF)

    dep = parse(*call("POST", "/deposit/depositions", {}), what="create")
    dep_id = dep["id"]
    bucket = dep["links"]["bucket"]
    print("draft", dep_id, "created")

    with open(PDF, "rb") as f:
        up = parse(*call("PUT", bucket + "/" + FILENAME, f.read(), ctype="application/octet-stream"),
                   what="upload")
    print("uploaded", up.get("key"), up.get("size"), "bytes (local", size, "bytes)")
    if up.get("size") != size:
        sys.exit("size mismatch: the server did not store what was sent")

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
    cmd = sys.argv[1] if len(sys.argv) > 1 else "draft"
    if cmd == "draft":
        draft()
    elif cmd == "show":
        show(sys.argv[2])
    elif cmd == "publish":
        publish(sys.argv[2])
    else:
        sys.exit(__doc__)
