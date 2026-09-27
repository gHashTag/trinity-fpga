#!/usr/bin/env node
// tern_tc_reopen_from_spec.mjs -- the reopen generation run's parameters, from its spec.
//
//   node conformance/tern_tc_reopen_from_spec.mjs            write the generated file
//   node conformance/tern_tc_reopen_from_spec.mjs --check    exit 1 if it drifted
//
// Source: specs/trinet/tern_tc_reopen_ax7203.t27. Compiled by the t27 compiler (wasm), its test
// blocks evaluated against its constants, as conformance/tern_tc_retransmit_from_spec.mjs does; the
// compiler and the AST helpers are imported from a gHashTag/trinity checkout (TRINITY_DIR, default
// ~/trinity), not copied.
//
// Output (path from the spec's GENERATED): conformance/tern_tc_reopen_params.py, a SPEC dict the
// runner conformance/tern_tc_generate_reopen_ax7203.py reads. The constants the spec repeats are read
// back from the generation and retransmit specs' generated params, so they cannot drift apart.

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { homedir } from 'node:os'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SPEC = 'specs/trinet/tern_tc_reopen_ax7203.t27'
const EXPECTED_MODULE = 'trinet_tern_tc_reopen_ax7203'
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

// Relations the test evaluator cannot state (no file reads). Every file of record is pinned by
// sha256; the repeated constants are compared with the params they come from; the coupling the
// reopen rests on (a flush write is a resync and nothing else) is read out of the sources.
const FROM_GENERATION = ['N_TOKENS', 'JOBS_EXPECTED', 'JOBS_PER_TOKEN_FULL', 'FIRST_JOB_NONCE',
  'SETKEY_NONCE', 'WINDOW', 'RESP_LEN', 'BAUD', 'NODE_ID']
const FROM_RETRANSMIT = ['REQ_LEN', 'REQ_BODY', 'RETRY_BASE', 'REFCELL_NONCE_FAULT_BIT', 'MAX_RETRANSMITS',
  'MAX_RESYNCS', 'FLUSH_BYTES', 'SERIAL_TIMEOUT_S', 'RESYNC_S_MAX', 'MIN_ANSWERS_PER_S', 'RX_HOLE_AT',
  'RX_HOLE_LEN', 'TX_DROP_AT', 'REHEARSAL_LOSSES', ['RT_MAX_ATTEMPTS', 'MAX_ATTEMPTS']]

const count = (text, re) => (text.match(re) ?? []).length

function semanticProblems(f) {
  const p = []
  const where = (file) => join(REPO, file)
  const read = (file) => (existsSync(where(file)) ? readFileSync(where(file), 'utf8') : '')
  for (const [file, sha] of [[f.GENERATE_SPEC_FILE, f.GENERATE_SPEC_SHA256],
    [f.GENERATE_PARAMS_FILE, f.GENERATE_PARAMS_SHA256], [f.GENERATE_RUNNER_FILE, f.GENERATE_RUNNER_SHA256],
    [f.HARNESS_FILE, f.HARNESS_SHA256], [f.NODE_RTL_FILE, f.NODE_RTL_SHA256], [f.PROTOCOL_FILE, f.PROTOCOL_SHA256],
    [f.RT_SPEC_FILE, f.RT_SPEC_SHA256], [f.RT_PARAMS_FILE, f.RT_PARAMS_SHA256],
    [f.RT_RUNNER_FILE, f.RT_RUNNER_SHA256], [f.REOPEN_FILE, f.REOPEN_SHA256]]) {
    if (!existsSync(where(file))) p.push(`${file} missing`)
    else if (sha256(readFileSync(where(file))) !== sha) p.push(`${file}: sha256 differs from the spec`)
  }
  const repeated = (paramsFile, keys) => {
    const params = read(paramsFile)
    for (const k of keys) {
      const [mine, theirs] = Array.isArray(k) ? k : [k, k]
      const m = params.match(new RegExp(`^    "${theirs}": (.+),$`, 'm'))
      if (!m || m[1] !== pyLiteral(f[mine])) p.push(`${mine} ${pyLiteral(f[mine])} != ${paramsFile} ${theirs} ${m ? m[1] : 'missing'}`)
    }
  }
  repeated(f.GENERATE_PARAMS_FILE, FROM_GENERATION)
  repeated(f.RT_PARAMS_FILE, FROM_RETRANSMIT)
  if (!read(f.RT_PARAMS_FILE).includes(`SPEC_SHA256 = "${f.RT_SPEC_SHA256}"`)) p.push('retransmit params were not generated from the pinned retransmit spec')

  // The flush is a resync and nothing else: the protocol writes exactly two things, the flush in
  // resync() and h.request(...); the harness writes only frames built by request(), which start AA 55.
  const proto = read(f.PROTOCOL_FILE)
  if (count(proto, /link\.write\(/g) !== 2 || count(proto, /link\.write\(bytes\(budget\.flush_bytes\)\)/g) !== 1 ||
      count(proto, /link\.write\(h\.request\(/g) !== 1) p.push('protocol no longer writes exactly one flush and one request kind')
  const flushInResync = proto.match(/def resync\(raw, why\):[\s\S]*?link\.write\(bytes\(budget\.flush_bytes\)\)[\s\S]*?\n\n/)
  if (!flushInResync) p.push('the flush write is not inside resync()')
  const harness = read(f.HARNESS_FILE)
  if (!/return bytes\(\[0xAA, 0x55, op\]\)/.test(harness)) p.push('harness request() no longer starts AA 55')
  if (!/def setkey_request\(key\):\n    return request\(/.test(harness)) p.push('harness setkey_request() no longer uses request()')
  if (count(harness, /link\.write\(/g) !== 2) p.push('harness writes something other than request frames')
  if (!/self\.ser = serial\.Serial\(port, baud, timeout=2\)\n        self\.ser\.reset_input_buffer\(\)/.test(harness)) {
    p.push('harness SerialLink no longer opens with timeout=2 and clears the input buffer')
  }

  // The link does what the spec says.
  const ro = read(f.REOPEN_FILE)
  if (!/if b == self\.flush:/.test(ro) || !/if self\.rx_since_flush == 0:\n\s+self\._reopen\(\)/.test(ro)) p.push('reopen link no longer reopens on a flush after zero bytes')
  if (!/wait = self\.wait_s \* 2 \*\* self\.reopens/.test(ro)) p.push('reopen wait no longer doubles per reopen')
  if (!/if self\.reopens >= self\.max_reopens:\n\s+raise ReopenExhausted/.test(ro)) p.push('reopen ceiling no longer raises ReopenExhausted')
  if (!/lambda: h\.SerialLink\(port, baud\)/.test(ro)) p.push('board link does not reopen through h.SerialLink')
  if (/^import tern_tc_retransmit_params|^from tern_tc_retransmit_params/m.test(ro)) p.push('reopen module must take its constants from the runner')

  let waits = 0
  for (let k = 0; k < f.MAX_REOPENS; k++) waits += f.REOPEN_WAIT_S * 2 ** k
  if (waits !== f.REOPEN_WAIT_TOTAL_S) p.push(`REOPEN_WAIT_TOTAL_S ${f.REOPEN_WAIT_TOTAL_S} != sum of the waits ${waits}`)
  if (f.REHEARSAL_STALLS !== 2) p.push('REHEARSAL_STALLS is not the stall schedule length (one answer-stream stall, one request-stream stall)')
  if (f.RX_HOLE_AT.length !== f.RX_HOLE_LEN.length) p.push('RX_HOLE_AT and RX_HOLE_LEN differ in length')
  if (f.RX_HOLE_AT.length + f.TX_DROP_AT.length !== f.REHEARSAL_LOSSES) p.push('REHEARSAL_LOSSES is not the schedule length')
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
    `# GENERATED by conformance/tern_tc_reopen_from_spec.mjs from ${SPEC} -- do not edit.`,
    '"""Reopen generation run parameters; the spec is the source, this file is a copy of it."""',
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
