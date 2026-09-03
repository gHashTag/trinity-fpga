#!/usr/bin/env python3
"""What every measurement record should have carried and none of them did.

The campaign's `weights/` directory lived in another session's `/tmp` scratchpad
and vanished mid-campaign (SUBSTRATE_IS_PERISHABLE_2026-08-12.md). It was
recovered and the ruler gate passed, so nothing was lost -- by luck, because
nothing recorded what the inputs actually were.

`gpt2` is not a version. `gpt2@<sha>` is. A corpus path is not a corpus: two
files at the same path can differ by a row and produce numbers that look exactly
like the old ones and are not comparable to them.

So: one call, emitted into every measurement record, that pins

  * the corpus by CONTENT -- sha256 of the exact joined text the harness feeds
    the tokeniser, plus row and character counts, so a restored copy is compared
    against what was used rather than against a description of it;
  * each checkpoint by REVISION -- the Hub commit sha where resolvable, the
    local safetensors' content hash otherwise, plus the parameter count;
  * the harness by the source it executed -- sha256 of block_tnf.py, since the
    measurement path is exec'd out of that file and a change to it changes the
    instrument.

    from provenance import corpus_fingerprint, checkpoint_fingerprint, harness_fingerprint
    out["provenance"] = {"corpus": corpus_fingerprint(txt, table),
                         "checkpoint": checkpoint_fingerprint(src),
                         "harness": harness_fingerprint()}

Nothing here asserts. A fingerprint that refuses to run is a fingerprint nobody
adds to their script; the assertion belongs in the ruler gate, which already
exists and already aborts. This only makes the comparison POSSIBLE later.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _sha256_file(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(1 << 20)
            if not b:
                break
            h.update(b)
            if limit and fh.tell() > limit:
                break
    return h.hexdigest()


def corpus_fingerprint(joined_text, table=None):
    """The text as the tokeniser sees it, not the file it came from.

    The join is part of the corpus: wikitext-2 rows joined with "\\n\\n" is a
    different string from the same rows joined with "\\n", and the perplexity
    differs. So the hash is of the joined text.
    """
    out = {"sha256": _sha256_text(joined_text), "chars": len(joined_text)}
    if table is not None:
        out["rows"] = int(table.num_rows)
    return out


def checkpoint_fingerprint(src):
    """Hub id + resolved revision where possible; content hash where not."""
    out = {"src": src}
    if os.path.isdir(src):
        out["kind"] = "local"
        shards = sorted(f for f in os.listdir(src) if f.endswith(".safetensors"))
        out["shards"] = shards
        # First 16 MiB of each shard: enough to separate two checkpoints, cheap
        # enough that nobody skips the call. Recorded as partial, not as "the"
        # hash, because a partial hash quoted as a full one is the kind of
        # overclaim this directory keeps finding.
        out["shard_sha256_first16MiB"] = {
            f: _sha256_file(os.path.join(src, f), limit=16 << 20) for f in shards}
        cfg = os.path.join(src, "config.json")
        if os.path.exists(cfg):
            out["config_sha256"] = _sha256_file(cfg)
    else:
        out["kind"] = "hub"
        try:
            from huggingface_hub import HfApi
            info = HfApi().model_info(src)
            out["revision"] = info.sha
        except Exception as e:                                    # noqa: BLE001
            # An unresolvable revision is recorded as unresolvable. Silently
            # omitting the field would read as "no revision needed".
            out["revision"] = None
            out["revision_error"] = f"{type(e).__name__}: {e}"[:200]
    return out


def harness_fingerprint(path=None):
    """The measurement path is exec'd out of block_tnf.py; hash what was exec'd."""
    path = path or os.path.join(HERE, "block_tnf.py")
    return {"file": os.path.basename(path), "sha256": _sha256_file(path)}


def describe(joined_text=None, table=None, src=None):
    out = {}
    if joined_text is not None:
        out["corpus"] = corpus_fingerprint(joined_text, table)
    if src is not None:
        out["checkpoint"] = checkpoint_fingerprint(src)
    out["harness"] = harness_fingerprint()
    return out


if __name__ == "__main__":
    import pyarrow.parquet as pq
    W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
         "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
    t = pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
    txt = "\n\n".join(t.column("text").to_pylist())
    print(json.dumps({"corpus": corpus_fingerprint(txt, t),
                      "harness": harness_fingerprint()}, indent=2))
