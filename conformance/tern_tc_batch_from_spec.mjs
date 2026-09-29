#!/usr/bin/env node
// tern_tc_batch_from_spec.mjs -- the batched wire protocol design's parameters, from its spec.
//
//   node conformance/tern_tc_batch_from_spec.mjs            write the generated file
//   node conformance/tern_tc_batch_from_spec.mjs --check    exit 1 if it drifted
//
// Source: specs/trinet/tern_tc_batch_ax7203.t27. Compiled by the t27 compiler (wasm), its test
// blocks evaluated against its constants, as conformance/tern_tc_retransmit_from_spec.mjs does;
// the compiler and the AST helpers are imported from a gHashTag/trinity checkout (TRINITY_DIR,
// default ~/trinity), not copied.
//
// Output (path from the spec's GENERATED): conformance/tern_tc_batch_params.py, a SPEC dict a
// future BatchCell reference model and runner read. No runner exists yet; the design's grounding
// lives in the semantic checks: every file of record is pinned by sha256, the constants repeated
// from the t27 reopen spec are read back out of that spec's text, the op codes are read back out
// of the harness and the MAC32 conformance source (and 0x03/0x04 must be absent from both), and
// the node RTL must still be the stateless AA-55 hunter the design's flush argument rests on.

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { homedir } from 'node:os'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SPEC = 'specs/trinet/tern_tc_batch_ax7203.t27'
const EXPECTED_MODULE = 'trinet_tern_tc_batch_ax7203'
const TRINITY = process.env.TRINITY_DIR ?? join(homedir(), 'trinity')
const SITE = join(TRINITY, 'apps', 'website')
const WASM = join(SITE, 'public', 't27', 't27_compiler.wasm')

const sha256 = (b) => createHash('sha256').update(b).digest('hex')

async function helpers() {
  for (const p of [WASM, join(SITE, 'scripts', 'agents-from-specs.mjs')]) {
    if (!existsSync(p)) throw new Error(`${p} not found; set TRINITY_DIR to a gHashTag/trinity checkout`)
  }
  const a = await import(pathToFileURL(join(SITE, 'scripts', 'agents-from-specs.mjs')).href)
  const v = await import(pathToFileURL(join(SITE, 'scripts', 'viewport-from-spec.mjs')).href)
  return { ...a, runSpecTests: v.runSpecTests }
}

// The constants this spec repeats from the t27 reopen spec, read back from that spec's text so the
// two cannot drift apart. The design's projections are arithmetic on JOBS_7T27; if the run's spec
// moves, this spec must be rewritten, not silently trusted.
const REPEATED = ['JOBS_EXPECTED', 'REQ_LEN', 'RESP_LEN', 'BAUD', 'WINDOW', 'FIRST_JOB_NONCE',
  'RETRY_BASE', 'MAX_RETRANSMITS', 'FLUSH_BYTES']
const REPEATS_AS = { JOBS_EXPECTED: 'JOBS_7T27' }

function semanticProblems(f) {
  const p = []
  const where = (file) => join(REPO, file)
  for (const [file, sha] of [[f.PLAN_DOC, f.PLAN_SHA256],
    [f.REOPEN_SPEC_FILE, f.REOPEN_SPEC_SHA256], [f.HARNESS_FILE, f.HARNESS_SHA256],
    [f.MAC32_FILE, f.MAC32_SHA256], [f.NODE_RTL_FILE, f.NODE_RTL_SHA256],
    [f.SIP_RTL_FILE, f.SIP_RTL_SHA256]]) {
    if (!existsSync(where(file))) p.push(`${file} missing`)
    else if (sha256(readFileSync(where(file))) !== sha) p.push(`${file}: sha256 differs from the spec`)
  }
  const reopen = existsSync(where(f.REOPEN_SPEC_FILE)) ? readFileSync(where(f.REOPEN_SPEC_FILE), 'utf8') : ''
  for (const k of REPEATED) {
    const m = reopen.match(new RegExp(`^pub const ${k} : \\w+ = (\\d+);`, 'm'))
    const mine = f[REPEATS_AS[k] ?? k]
    if (!m || Number(m[1]) !== mine) p.push(`${REPEATS_AS[k] ?? k} ${mine} != reopen spec ${m ? m[1] : 'missing'}`)
  }
  // the op codes the design builds on are the live ones, and the codes it claims are free
  const mac32 = existsSync(where(f.MAC32_FILE)) ? readFileSync(where(f.MAC32_FILE), 'utf8') : ''
  const harness = existsSync(where(f.HARNESS_FILE)) ? readFileSync(where(f.HARNESS_FILE), 'utf8') : ''
  const om = mac32.match(/^OP_MAC32 = (0x[0-9A-Fa-f]+|\d+)$/m)
  const os = harness.match(/^OP_SETKEY = (0x[0-9A-Fa-f]+|\d+)$/m)
  if (!om || Number(om[1]) !== f.OP_MAC32) p.push(`OP_MAC32 ${f.OP_MAC32} != MAC32 conformance ${om ? om[1] : 'missing'}`)
  if (!os || Number(os[1]) !== f.OP_SETKEY) p.push(`OP_SETKEY ${f.OP_SETKEY} != harness ${os ? os[1] : 'missing'}`)
  for (const [name, src] of [['MAC32 conformance', mac32], ['harness', harness]]) {
    if (/^OP_\w+ = 0x0[34]$/m.test(src)) p.push(`${name} already defines an op 0x03/0x04; this design's op codes are taken`)
  }
  if (!/^def request\(op, nonce, w, x\):/m.test(harness)) p.push('harness request() signature changed; frame anatomy readback is stale')
  if (!/return bytes\(\[0xAA, 0x55, op\]\) \+ nonce\.to_bytes\(4, "little"\) \+ w \+ x \+ b"\\x00"/m.test(harness)) {
    p.push('harness request() no longer builds AA 55 | op | nonce4 | w | x | 00')
  }
  const rtl = existsSync(where(f.NODE_RTL_FILE)) ? readFileSync(where(f.NODE_RTL_FILE), 'utf8') : ''
  if (!/F_MAGIC0: fstate <= \(rx_byte == 8'hAA\)/.test(rtl) || !/if \(rx_byte == 8'h55\) begin fstate <= F_BODY/.test(rtl)) {
    p.push('node RTL no longer hunts for AA 55')
  }
  const last = rtl.match(/if \(bidx == 5'd(\d+)\) begin\s*frame_valid <= 1'b1;/)
  if (!last || Number(last[1]) + 1 !== f.REQ_BODY) p.push(`node RTL frame body is ${last ? Number(last[1]) + 1 : '?'} bytes, spec REQ_BODY ${f.REQ_BODY}`)
  const plan = existsSync(where(f.PLAN_DOC)) ? readFileSync(where(f.PLAN_DOC), 'utf8') : ''
  for (const anchor of ['1,118,816', '26.9 MB', '161,109,504', '235 s']) {
    if (!plan.includes(anchor)) p.push(`plan doc no longer carries its ${anchor} projection`)
  }
  if (f.BATCH_K !== f.WINDOW) p.push('BATCH_K is not WINDOW')
  if (f.RESP_DOT6_LEN !== f.REQ_LEN) p.push('DOT6 answer length is not the request length (streams unbalanced)')
  return p
}

function pyLiteral(v) {
  if (typeof v === 'boolean') return v ? 'True' : 'False'
  if (Array.isArray(v)) return `[${v.map(pyLiteral).join(', ')}]`
  return JSON.stringify(v)
}

function renderPython(f, specSha, wasmSha) {
  const keys = Object.keys(f).sort()
  return [
    `# GENERATED by conformance/tern_tc_batch_from_spec.mjs from ${SPEC} -- do not edit.`,
    '"""Batched wire protocol design parameters; the spec is the source, this file is a copy of it."""',
    '',
    `SPEC_FILE = ${JSON.stringify(SPEC)}`,
    `SPEC_SHA256 = ${JSON.stringify(specSha)}`,
    `COMPILER_WASM_SHA256 = ${JSON.stringify(wasmSha)}`,
    '',
    'SPEC = {',
    ...keys.map((k) => `    ${JSON.stringify(k)}: ${pyLiteral(f[k])},`),
    '}',
    '',
  ].join('\n')
}

export async function build() {
  const h = await helpers()
  const wasmBytes = readFileSync(WASM)
  const analyze = await h.loadCompiler(wasmBytes)
  const specText = readFileSync(join(REPO, SPEC), 'utf8')
  const problems = []
  const analysis = analyze(specText)
  const verdict = h.verdictOf(analysis)
  if (!verdict.typecheckOk || verdict.errors > 0 || verdict.discarded > 0 || !verdict.hirOk) problems.push(`compiler verdict not clean ${JSON.stringify(verdict)}`)
  problems.push(...h.compilerErrors(analysis))
  if (/[^\x00-\x7f]/.test(specText)) problems.push('non-ASCII byte in the spec')
  const moduleName = analysis.ast?.name ?? null
  if (moduleName !== EXPECTED_MODULE) problems.push(`module must be ${EXPECTED_MODULE}, is ${moduleName}`)
  let f = {}
  try {
    f = Object.fromEntries(Object.entries(h.constsOf(analysis)).map(([k, v]) => [k, v.value]))
  } catch (e) {
    problems.push(e.message)
  }
  let tests = { tests: 0, asserts: 0, failures: [] }
  if (problems.length === 0) {
    tests = h.runSpecTests(analysis, f)
    if (tests.tests === 0 || tests.asserts === 0) problems.push('no test block or no assert; the spec must test its own invariants')
    problems.push(...tests.failures.map((m) => `test ${m}`))
    problems.push(...semanticProblems(f))
  }
  const specSha = sha256(Buffer.from(specText, 'utf8'))
  const wasmSha = sha256(wasmBytes)
  const out = problems.length ? null : { [f.GENERATED[0]]: renderPython(f, specSha, wasmSha) }
  return { problems, verdict, tests, consts: Object.keys(f).length, specSha, wasmSha, out }
}

async function main() {
  const check = process.argv.includes('--check')
  const r = await build()
  console.log(`spec ${SPEC} sha256 ${r.specSha.slice(0, 16)}  wasm ${r.wasmSha.slice(0, 16)}  verdict ${JSON.stringify(r.verdict)}`)
  console.log(`constants ${r.consts}  tests ${r.tests.tests}  asserts ${r.tests.asserts}  failures ${r.tests.failures.length}`)
  if (r.problems.length) {
    for (const p of r.problems) console.log(`PROBLEM ${p}`)
    process.exit(1)
  }
  let drift = 0
  for (const [rel, text] of Object.entries(r.out)) {
    const path = join(REPO, rel)
    const cur = existsSync(path) ? readFileSync(path, 'utf8') : null
    if (cur === text) { console.log(`same   ${rel}`); continue }
    if (check) { console.log(`DRIFT  ${rel}`); drift++; continue }
    mkdirSync(dirname(path), { recursive: true })
    writeFileSync(path, text)
    console.log(`wrote  ${rel}`)
  }
  process.exit(drift ? 1 : 0)
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) main().catch((e) => { console.error(e.message); process.exit(2) })
