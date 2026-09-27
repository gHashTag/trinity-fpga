#!/usr/bin/env node
// mxdot4_board_from_spec.mjs -- the MXFP4/TNF4 block-dot cell's parameters, generated from its spec.
//
//   node conformance/mxdot4_board_from_spec.mjs            write the two generated files
//   node conformance/mxdot4_board_from_spec.mjs --check    exit 1 if either file drifted
//
// Source: specs/trinet/mxdot4_on_board_ax7203.t27. Compiled by the t27 compiler (wasm), its test
// blocks evaluated against its constants, as conformance/tnf16_board_from_spec.mjs does; the
// compiler and the AST helpers are imported from a gHashTag/trinity checkout (TRINITY_DIR,
// default ~/trinity), not copied.
//
// Outputs (paths come from the spec's GENERATED):
//   fpga/tnet/mxdot4_board_params.v      `define MXDOT4_* macros for the RTL and testbenches
//   conformance/mxdot4_board_params.py   SPEC dict for the host, the vectors and the golden

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { homedir } from 'node:os'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SPEC = 'specs/trinet/mxdot4_on_board_ax7203.t27'
const EXPECTED_MODULE = 'trinet_mxdot4_on_board_ax7203'
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

// Relations the test evaluator cannot state (no powers, no loops, no file reads). The level
// values themselves are checked against mxfp_ref.py and block_tnf.py by the Python golden,
// which can run those files; here only their bytes are pinned.
function semanticProblems(f) {
  const p = []
  const increasing = (xs) => xs.every((x, i) => i === 0 || x > xs[i - 1])
  if (f.MAG_CODES !== 2 ** (f.ELEM_BITS - 1)) p.push('MAG_CODES != 2^(ELEM_BITS-1)')
  if (f.SIGN_BIT !== 2 ** (f.ELEM_BITS - 1)) p.push('SIGN_BIT != 2^(ELEM_BITS-1)')
  if (f.SUM_LIMIT !== 2 ** (f.SUM_BITS - 1)) p.push('SUM_LIMIT != 2^(SUM_BITS-1)')
  if (f.EXP_LIMIT !== 2 ** f.EXP_BITS) p.push('EXP_LIMIT != 2^EXP_BITS')
  if (f.NAN_WORD !== 2 ** f.NAN_BIT) p.push('NAN_WORD != 2^NAN_BIT')
  if (f.EDGE_PER_OP !== 2 ** (2 * f.ELEM_BITS)) p.push('EDGE_PER_OP != 2^(2*ELEM_BITS)')
  if (f.SCALE_PAIRS_PER_OP !== 2 ** 16) p.push('SCALE_PAIRS_PER_OP != 2^16')
  if (f.E2M1_INT.length !== f.MAG_CODES || f.TNF4_INT.length !== f.MAG_CODES) p.push('a level table is not MAG_CODES long')
  if (!increasing(f.E2M1_INT)) p.push('E2M1_INT not strictly increasing')
  if (!increasing(f.TNF4_INT.slice(0, f.TNF4_LEVELS))) p.push('TNF4_INT levels not strictly increasing')
  if (f.TNF4_HOLE_CODE !== f.TNF4_LEVELS) p.push('TNF4_HOLE_CODE is not the code after the last level')
  if (!increasing(f.TNF4_AT_E2M1)) p.push('TNF4_AT_E2M1 not strictly increasing')
  const missing = [...f.E2M1_INT.keys()].filter((c) => !f.TNF4_AT_E2M1.includes(c))
  if (missing.length !== 1 || missing[0] !== f.E2M1_ONLY_CODE) p.push(`E2M1 codes without a TNF4 level: ${missing} (spec says ${f.E2M1_ONLY_CODE})`)
  if (Math.max(...f.E2M1_INT) ** 2 !== f.PROD_MAX || Math.max(...f.TNF4_INT) ** 2 !== f.PROD_MAX) p.push('PROD_MAX is not a table top squared')
  if (Math.max(...f.E2M1_INT, ...f.TNF4_INT) >= 2 ** f.ELEM_BITS) p.push('a table entry does not fit ELEM_BITS')
  if (f.CP2102N_N !== Math.round(f.CP2102N_REF_HZ / f.HOST_BAUD)) p.push('HOST_BAUD does not select CP2102N_N')
  if (f.WIRE_BAUD !== Math.floor(f.CP2102N_REF_HZ / f.CP2102N_N)) p.push('WIRE_BAUD != floor(24 MHz / N)')
  if (f.PASS_LINE !== `MXDOT4 RESULT: ${f.TOTAL_REQUESTS}/${f.TOTAL_REQUESTS} bit-exact (fails=0, lost=0)`) p.push(`PASS_LINE does not name ${f.TOTAL_REQUESTS}/${f.TOTAL_REQUESTS}`)
  if (f.SIM_PASS_LINE !== `MXDOT4 SIM: ${f.TOTAL_REQUESTS}/${f.TOTAL_REQUESTS} bit-exact (fails=0)`) p.push(`SIM_PASS_LINE does not name ${f.TOTAL_REQUESTS}/${f.TOTAL_REQUESTS}`)
  for (const [file, want] of [[f.MXFP_REF_FILE, f.MXFP_REF_SHA256], [f.TNF_LEVELS_FILE, f.TNF_LEVELS_SHA256]]) {
    const path = join(REPO, file)
    if (!existsSync(path)) p.push(`${file} missing`)
    else if (sha256(readFileSync(path)) !== want) p.push(`${file}: sha256 differs from the spec`)
  }
  return p
}

// Eight 4-bit entries packed as one hex word, entry k at bits 4k+3..4k.
const packTable = (xs) => xs.reduceRight((acc, x) => acc * 16 + x, 0).toString(16).toUpperCase().padStart(8, '0')

// Only what the RTL needs, as macros: yosys and iverilog both carry a `define across files.
function renderVerilog(f, specSha, wasmSha) {
  const d = (name, width, value) => `\`define MXDOT4_${name} ${width}'d${value}`
  return [
    `// GENERATED by conformance/mxdot4_board_from_spec.mjs from ${SPEC} -- do not edit.`,
    `// spec sha256 ${specSha}`,
    `// t27 compiler wasm sha256 ${wasmSha}`,
    '`ifndef MXDOT4_BOARD_PARAMS',
    '`define MXDOT4_BOARD_PARAMS',
    d('BLOCK', 8, f.BLOCK),
    d('ELEM_BITS', 8, f.ELEM_BITS),
    d('SUM_BITS', 8, f.SUM_BITS),
    d('EXP_BITS', 8, f.EXP_BITS),
    d('WORD_BITS', 8, f.WORD_BITS),
    d('NAN_WORD', 24, f.NAN_WORD),
    d('SCALE_NAN', 8, f.SCALE_NAN),
    `\`define MXDOT4_E2M1_TABLE 32'h${packTable(f.E2M1_INT)}`,
    `\`define MXDOT4_TNF4_TABLE 32'h${packTable(f.TNF4_INT)}`,
    d('BAUD_DIV', 10, f.BAUD_DIV),
    d('SYNC0', 8, f.SYNC0),
    d('SYNC1', 8, f.SYNC1),
    d('RESP_OK', 8, f.RESP_OK),
    d('RESP_BADOP', 8, f.RESP_BADOP),
    d('OP_MXFP4', 8, f.OP_MXFP4),
    d('OP_TNF4', 8, f.OP_TNF4),
    d('REQ_BYTES', 8, f.REQ_BYTES),
    d('RESP_BYTES', 8, f.RESP_BYTES),
    d('CORE_STAGES', 8, f.CORE_STAGES),
    '`endif',
    '',
  ].join('\n')
}

function pyLiteral(v) {
  if (typeof v === 'boolean') return v ? 'True' : 'False'
  if (Array.isArray(v)) return `[${v.map(pyLiteral).join(', ')}]`
  return JSON.stringify(v)
}

function renderPython(f, specSha, wasmSha) {
  const keys = Object.keys(f).sort()
  return [
    `# GENERATED by conformance/mxdot4_board_from_spec.mjs from ${SPEC} -- do not edit.`,
    '"""MXFP4/TNF4 block-dot cell parameters; the spec is the source, this file is a copy of it."""',
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
  const out = problems.length ? null : {
    [f.GENERATED[0]]: renderVerilog(f, specSha, wasmSha),
    [f.GENERATED[1]]: renderPython(f, specSha, wasmSha),
  }
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
