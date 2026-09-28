---
name: gpu-finetune
description: "Rent a RunPod GPU pod, fine-tune a local model, export, and stop the pod — without printing the API key or touching fleet pods. The REST/GraphQL traps, corpus shims, and cost discipline learned doing the t27 fine-tune ($0.58 total)."
---

# GPU fine-tune on RunPod — the flow that worked

Reference run: tern_tc (TC02, 9M params) fine-tuned on the 8K-tokenized t27
FIM corpus, 337 steps, val bpb 0.756 → 0.611, 2026-09-28, total cost $0.58.

## Key discipline (absolute)

- The API key lives in a file (`/tmp/rpk2.txt`). **Never print it** — only
  masked fingerprints. Values flow file→env *inside one Bash call*:
  `RUNPOD_API_KEY=$(cat /tmp/rpk2.txt) python3 …`.
- **Never touch the 20 fleet pods** (all EXITED; leave them). Balance is the
  owner's money: check `balance()` before and after, record both numbers.
- One pod, one job, STOP it the moment training ends. A stopped pod stops
  billing compute (storage may still bill — delete if the outputs are copied
  out).

## API shape (learned the hard way)

`~/igla-coder-gpu/rp.py` is the client (stdlib only): `gql()` for GraphQL
(`https://api.runpod.io/graphql`), `rest()` for REST (`https://rest.runpod.io/v1`).

- **Cloudflare rejects the default Python-urllib User-Agent (error 1010).**
  Every request sends its own UA.
- **GraphQL for pod mutations** — the REST pod-creation endpoint rejects
  request bodies the GraphQL mutation accepts (schema strictness differs).
  Use GraphQL for create/stop; REST GET is fine for `/pods` and pod state.
- **Discover valid `gpuTypeIds` by probing**: POST an invalid one and the
  400 error *lists the whole enum* (`'AMD Instinct MI300X OAM'`,
  `'NVIDIA A100 80GB PCIe'`, …). Cheaper than any docs page.
- **Volumes are region-locked**: the corpus volume lived on EU-RO-1, so the pod
  had to land in EU-RO-1 too. A pod in another region cannot attach it.
- Balance query: `{ myself { id clientBalance currentSpendPerHr spendLimit underBalance } }`.

## Corpus and training

- Corpus build: `t27_bench.py fim` over the t27 repo's items.jsonl with the
  project's own 8K tokenizer (`artifacts/tokenizers/data8k_tokenizer.json`).
- **pyarrow shim**: `data.py`'s parquet import stack is unnecessary for fim —
  shim a `types.ModuleType("data")` carrying exactly what `cmd_fim` reads
  (`EOT, FIM_PREFIX, FIM_MIDDLE, FIM_SUFFIX, token_bytes`), copied verbatim
  from data.py (see `/tmp/fim8k_driver.py`). Import the shim *before*
  `t27_bench`.
- Upload with `rsync -a --progress src/ pod:/workspace/dst/` — **the trailing
  slash matters** (contents vs the directory itself).
- Export to the project's binary format on the pod, copy out, and **record the
  sha256 immediately** — it becomes `MODEL_SHA256` in the pre-registration
  spec (see the `t27-spec` skill for the pin doctrine).

## Before/after demo before any board run

Run the base and tuned model on the same prompt locally and save both outputs
(`/tmp/t27_prompt_demo_tuned.py`, MODEL pointed at the new bin). Expect
structurally-right-but-factually-wrong text: one clean line is not a program,
and that honesty belongs in the spec's WHAT IT DOES NOT SAY.
