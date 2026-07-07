#!/usr/bin/env python3
"""tier_e_counter.py — Automatic Tier-E counter for #199."""
import re, json, sys, subprocess, argparse

ISSUE = "199"
REPO = "gHashTag/trinity-fpga"

def fetch_comments():
    all_c = []
    page = 1
    while True:
        r = subprocess.run(
            ["gh", "api", f"repos/{REPO}/issues/{ISSUE}/comments?per_page=100&page={page}"],
            capture_output=True, text=True)
        batch = json.loads(r.stdout)
        if not batch: break
        all_c.extend(batch)
        page += 1
    return all_c

RE_SHA = re.compile(r'\b[0-9a-f]{8,}\b', re.I)
RE_IDCODE = re.compile(r'0x13636093', re.I)
# CI witness: strongest form is a numeric run-id (>=8 digits, possibly in an
# actions/runs/ URL). Some proofs record only a textual "CI run: ... SUCCESS"
# line without pasting the run-id. Both count as a CI witness, but only the
# numeric run-id is auditable (main() flags proofs that lack it).
RE_CI_RUNID = re.compile(r'(?:actions/runs/)?\b(\d{8,})\b')
RE_CI_TEXT = re.compile(r'\bCI[\s-]*run\b.*?\bSUCCESS\b', re.I)
RE_UART = re.compile(r'(\d+)\s*/\s*(\d+).*?(?:bit-exact|fails\s*=\s*0)', re.I)
RE_HEADER = re.compile(r'###\s+Tier-E\s+(re-)?proofs?\s*:\s*(.*)', re.I)
RE_FMT_BTICK = re.compile(r'`([a-z][a-z0-9_]*(?:-[a-z]+)?)`', re.I)
RE_OP_SUFFIX = re.compile(r'-(?:add|mul|sub)$', re.I)

def parse_comment(body):
    """Extract proofs from one comment."""
    m = RE_HEADER.search(body)
    if not m: return []
    is_reproof = bool(m.group(1))
    header_rest = m.group(2).split('\n')[0]  # rest of header line only

    # Determine op
    lower = header_rest.lower()
    if 'decode' in lower: op = 'decode'
    elif any(x in lower for x in ['compute','add','mul','sub']): op = 'compute'
    else: op = 'unknown'

    # Extract format names from header line
    # Strategy: find backtick-delimited tokens first
    btick_fmts = RE_FMT_BTICK.findall(header_rest)
    if btick_fmts:
        fmts = [RE_OP_SUFFIX.sub('', f.lower()) for f in btick_fmts]
    else:
        # No backticks: extract words that look like format names
        # Remove op keywords and common words from the header line
        cleaned = re.sub(r'\([^)]*\)', '', header_rest)  # remove parenthetical
        cleaned = re.sub(r'\b(?:DECODE|COMPUTE|NEW|cell|cells|chain|exhaustive|'
                        r'Tier-E|proof|proofs|no-flatten|fix|wider-frame|re-flash|'
                        r'on|silicon|first|each|re-proof|reproof|correctness|'
                        r'subnormal-flush|matched-substrate|4/4|HW|cell|op|FP32)\b',
                        '', cleaned, flags=re.I)
        # Split on + / , & and whitespace
        tokens = re.split(r'[+,/&]|\s+', cleaned.strip())
        fmts = []
        for t in tokens:
            t = t.strip().lower().lstrip('`').rstrip('`').strip('*')
            t = RE_OP_SUFFIX.sub('', t)
            # Keep only if looks like a format name: starts with letter, has alnum
            if re.match(r'^[a-z][a-z0-9_]+$', t) and len(t) >= 2 and len(t) <= 20:
                fmts.append(t)

    # Deduplicate within this comment
    seen = set()
    unique_fmts = []
    for f in fmts:
        if f not in seen:
            seen.add(f)
            unique_fmts.append(f)

    # 4/4 chain validation (shared across all formats in comment)
    sha = RE_SHA.search(body)
    uart = RE_UART.search(body)
    idcode = RE_IDCODE.search(body)
    ci_runid = RE_CI_RUNID.search(body)
    ci_text = RE_CI_TEXT.search(body)
    ci = ci_runid or ci_text
    chain = all([sha, uart, idcode, ci])

    return [{'format': f, 'op': op, 'chain_4_4': chain, 'is_reproof': is_reproof,
             'sha': bool(sha), 'uart': bool(uart), 'idcode': bool(idcode),
             'ci': bool(ci), 'ci_runid': bool(ci_runid)}
            for f in unique_fmts]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    comments = fetch_comments()
    proofs = []
    for c in comments:
        proofs.extend(parse_comment(c.get('body', '')))

    valid = [p for p in proofs if p['chain_4_4']]

    # Deduplicate by (format, op)
    cells = {}
    for p in valid:
        k = (p['format'], p['op'])
        if k not in cells:
            cells[k] = p
    unique = list(cells.values())

    dec = sorted(set(p['format'] for p in unique if p['op'] == 'decode'))
    comp = sorted(set(p['format'] for p in unique if p['op'] == 'compute'))
    union = sorted(set(dec) | set(comp))
    both = sorted(set(dec) & set(comp))
    no_chain = [p for p in proofs if not p['chain_4_4']]
    # Valid proofs whose CI witness is only textual ("CI run: SUCCESS") and lack an
    # auditable numeric run-id. They count, but should be upgraded with the run-id.
    no_runid = sorted(set(p['format'] for p in unique if not p.get('ci_runid')))

    if args.json:
        out = {
            'decode_hw_unique': len(dec), 'decode_formats': dec,
            'compute_hw_unique': len(comp), 'compute_formats': comp,
            'cellop_total': len(unique), 'union_unique': len(union),
            'both_axes': both, 'both_axes_count': len(both),
            'parsed': len(proofs), 'chain_4_4': len(valid), 'no_chain': len(no_chain),
            'valid_no_runid': no_runid,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print(f"{'='*60}")
    print(f"Tier-E Live Counter — #{ISSUE}")
    print(f"{'='*60}")
    print(f"Parsed: {len(proofs)} | 4/4: {len(valid)} | no-chain: {len(no_chain)}\n")
    print(f"  decode-HW unique:  {len(dec)}")
    print(f"  compute-HW unique: {len(comp)}")
    print(f"  (cell,op) total:   {len(unique)}")
    print(f"  union (≥1 axis):   {len(union)}")
    print(f"  both axes (3/3):   {len(both)}")
    if both: print(f"    → {', '.join(both)}")
    if no_chain:
        print(f"\n⚠ {len(no_chain)} without 4/4 chain")
    if no_runid:
        print(f"⚠ {len(no_runid)} valid but no numeric CI run-id (upgrade recommended):")
        print(f"    → {', '.join(no_runid)}")
    if args.verbose:
        print(f"\n--- decode ({len(dec)}) ---")
        for f in dec: print(f"  {f}")
        print(f"--- compute ({len(comp)}) ---")
        for f in comp: print(f"  {f}")

if __name__ == '__main__':
    main()
