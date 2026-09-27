#!/usr/bin/env node
// tern_tc_retransmit_from_spec.mjs -- the retransmit generation run's parameters, from its spec.
//
//   node conformance/tern_tc_retransmit_from_spec.mjs            write the generated file
//   node conformance/tern_tc_retransmit_from_spec.mjs --check    exit 1 if it drifted
//
// Source: specs/trinet/tern_tc_retransmit_ax7203.t27. Compiled by the t27 compiler (wasm), its test
// blocks evaluated against its constants, as conformance/mxdot4_board_from_spec.mjs does; the
// compiler and the AST helpers are imported from a gHashTag/trinity checkout (TRINITY_DIR,
// default ~/trinity), not copied.
//
// Output (path from the spec's GENERATED): conformance/tern_tc_retransmit_params.py, a SPEC dict the
// runner conformance/tern_tc_generate_rt_ax7203.py reads. The constants the spec repeats from the
// generation spec are read back from that spec's generated params, so the two cannot drift apart.

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { homedir } from 'node:os'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SPEC = 'specs/trinet/tern_tc_retransmit_ax7203.t27'
const EXPECTED_MODULE = 'trinet_tern_tc_retransmit_ax7203'
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
// sha256; the constants repeated from the generation spec are compared with its generated params;
// the node frame and the harness constants are read back out of their sources.
const REPEATED = ['N_TOKENS', 'JOBS_EXPECTED', 'JOBS_PER_TOKEN_FULL', 'FIRST_JOB_NONCE', 'SETKEY_NONCE',
  'WINDOW', 'RESP_LEN', 'BAUD', 'NODE_ID']

function semanticProblems(f) {
  const p = []
  const where = (file) => join(REPO, file)
  for (const [file, sha] of [[f.GENERATE_SPEC_FILE, f.GENERATE_SPEC_SHA256],
    [f.GENERATE_PARAMS_FILE, f.GENERATE_PARAMS_SHA256], [f.GENERATE_RUNNER_FILE, f.GENERATE_RUNNER_SHA256],
    [f.HARNESS_FILE, f.HARNESS_SHA256], [f.NODE_RTL_FILE, f.NODE_RTL_SHA256], [f.PROTOCOL_FILE, f.PROTOCOL_SHA256]]) {
    if (!existsSync(where(file))) p.push(`${file} missing`)
    else if (sha256(readFileSync(where(file))) !== sha) p.push(`${file}: sha256 differs from the spec`)
  }
  const params = existsSync(where(f.GENERATE_PARAMS_FILE)) ? readFileSync(where(f.GENERATE_PARAMS_FILE), 'utf8') : ''
  for (const k of REPEATED) {
    const m = params.match(new RegExp(`^    "${k}": (\\d+),$`, 'm'))
    if (!m || Number(m[1]) !== f[k]) p.push(`${k} ${f[k]} != generation params ${m ? m[1] : 'missing'}`)
  }
  const harness = existsSync(where(f.HARNESS_FILE)) ? readFileSync(where(f.HARNESS_FILE), 'utf8') : ''
  const num = (name) => {
    const m = harness.match(new RegExp(`^${name} = (0x[0-9A-Fa-f]+|\\d+)`, 'm'))
    return m ? Number(m[1]) : null
  }
  for (const k of ['RESP_LEN', 'FIRST_JOB_NONCE', 'SETKEY_NONCE']) {
    if (num(k) !== f[k]) p.push(`${k} ${f[k]} != harness ${num(k)}`)
  }
  if (!/\^ 0x40000000/.test(harness)) p.push("harness RefCell 'nonce' fault no longer XORs 0x40000000")
  if (f.REFCELL_NONCE_FAULT_BIT !== 0x40000000) p.push('REFCELL_NONCE_FAULT_BIT is not 0x40000000')
  if (f.RETRY_BASE !== 0x20000000) p.push('RETRY_BASE is not 0x20000000')
  if (!/timeout=2\)/.test(harness)) p.push(`harness SerialLink timeout is not ${f.SERIAL_TIMEOUT_S} s`)
  const rtl = existsSync(where(f.NODE_RTL_FILE)) ? readFileSync(where(f.NODE_RTL_FILE), 'utf8') : ''
  if (!/F_MAGIC0: fstate <= \(rx_byte == 8'hAA\)/.test(rtl) || !/if \(rx_byte == 8'h55\) begin fstate <= F_BODY/.test(rtl)) {
    p.push('node RTL no longer hunts for AA 55')
  }
  const last = rtl.match(/if \(bidx == 5'd(\d+)\) begin\s*frame_valid <= 1'b1;/)
  if (!last || Number(last[1]) + 1 !== f.REQ_BODY) p.push(`node RTL frame body is ${last ? Number(last[1]) + 1 : '?'} bytes, spec REQ_BODY ${f.REQ_BODY}`)
  const proto = existsSync(where(f.PROTOCOL_FILE)) ? readFileSync(where(f.PROTOCOL_FILE), 'utf8') : ''
  if (!/^DRAIN_CHUNK = \d+$/m.test(proto)) p.push('protocol file has no DRAIN_CHUNK')
  if (f.RX_HOLE_AT.length !== f.RX_HOLE_LEN.length) p.push('RX_HOLE_AT and RX_HOLE_LEN differ in length')
  if (f.RX_HOLE_AT.length + f.TX_DROP_AT.length !== f.REHEARSAL_LOSSES) p.push('REHEARSAL_LOSSES is not the schedule length')
  if (f.NODE_ID !== 0x5452494e) p.push('NODE_ID is not 0x5452494e')
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
    `# GENERATED by conformance/tern_tc_retransmit_from_spec.mjs from ${SPEC} -- do not edit.`,
    '"""Retransmit generation run parameters; the spec is the source, this file is a copy of it."""',
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
