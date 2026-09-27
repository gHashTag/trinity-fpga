#!/usr/bin/env node
// ternary_storage_v2_from_spec.mjs -- the second ternary-storage search's parameters, from its spec.
//
//   node conformance/ternary_storage_v2_from_spec.mjs            write the generated file
//   node conformance/ternary_storage_v2_from_spec.mjs --check    exit 1 if it drifted
//
// Source: specs/numeric/ternary_storage_search_v2.t27. Compiled by the t27 compiler (wasm), its test
// blocks evaluated against its constants, as conformance/mxdot4_board_from_spec.mjs does; the
// compiler and the AST helpers are imported from a gHashTag/trinity checkout (TRINITY_DIR,
// default ~/trinity), not copied.
//
// It also compiles the first attempt's spec and fails if a constant named in SHARED_WITH_V1 differs,
// and reads the ruler values out of the first attempt's log text.
//
// Output (path from the spec's GENERATED): research/block/ternary_storage_v2_params.py, a SPEC dict
// the runner research/block/ternary_storage_search_v2.py reads.

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { homedir } from 'node:os'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SPEC = 'specs/numeric/ternary_storage_search_v2.t27'
const EXPECTED_MODULE = 'numeric_ternary_storage_search_v2'
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
// tables against block_tnf.py's own functions, and T27_N against NormalDist, are checked by the
// runner, which can execute them; here only the bytes of block_tnf.py are pinned.
function semanticProblems(f, v1) {
  const p = []
  const increasing = (xs) => xs.every((x, i) => i === 0 || x > xs[i - 1])
  for (const name of ['E2M1', 'TNF4_7', 'E2M2', 'T27_U', 'T27_F', 'T27_N', 'MXP_BM_HALF']) {
    if (!Array.isArray(f[name]) || !increasing(f[name])) p.push(`${name} not strictly increasing`)
  }
  // one truth: every shared constant is the first attempt's, value for value
  for (const k of f.SHARED_WITH_V1) {
    if (!(k in f)) p.push(`${k} named in SHARED_WITH_V1 but not defined here`)
    else if (!(k in v1)) p.push(`${k} not in the first attempt's spec`)
    else if (JSON.stringify(f[k]) !== JSON.stringify(v1[k])) p.push(`${k} differs from ${f.V1_SPEC}`)
  }
  if (new Set(f.SHARED_WITH_V1).size !== f.SHARED_WITH_V1.length) p.push('SHARED_WITH_V1 repeats a name')
  // the rulers are the first attempt's log text, not typed from memory
  const logPath = join(REPO, f.V1_LOG)
  if (!existsSync(logPath)) p.push(`${f.V1_LOG} missing`)
  else {
    const buf = readFileSync(logPath)
    if (sha256(buf) !== f.V1_LOG_SHA256) p.push(`${f.V1_LOG}: sha256 differs from the spec`)
    const txt = buf.toString('utf8')
    for (const [arm, rule, key] of [['BASE', '-', 'RULER_BASE_E4'], ['E2M1', 'B', 'RULER_MXFP4_B_E4'], ['TNF4_7', 'B', 'RULER_TNF4_7_B_E4']]) {
      const m = txt.match(new RegExp(`ARM ruler test ${arm}\\s+rule ${rule}\\s+ppl (\\d+)\\.(\\d{4})`))
      if (!m) p.push(`${f.V1_LOG}: no ruler row for ${arm}`)
      else if (Number(m[1] + m[2]) !== f[key]) p.push(`${key} ${f[key]} != the log's ${m[1]}.${m[2]}`)
    }
    for (const [key, main] of [['RULER_BASE_E4', 'MAIN_BASE_E4'], ['RULER_MXFP4_B_E4', 'MAIN_MXFP4_B_E4'], ['RULER_TNF4_7_B_E4', 'MAIN_TNF4_7_B_E4']]) {
      const vk = { MAIN_BASE_E4: 'RULER_BASE_E4', MAIN_MXFP4_B_E4: 'RULER_MXFP4_B_E4', MAIN_TNF4_7_B_E4: 'RULER_TNF4_7_B_E4' }[main]
      if (f[main] !== v1[vk]) p.push(`${main} ${f[main]} != the first attempt's main value ${v1[vk]}`)
    }
  }
  const e2m2Missing = [...f.E2M2.keys()].filter((c) => !f.T27_F_AT_E2M2.includes(c))
  if (e2m2Missing.join(',') !== '1,3') p.push(`E2M2 codes without a T27_F level: ${e2m2Missing}`)
  const trits = (codes) => Math.ceil(Math.log(codes) / Math.log(3) - 1e-12)
  if (trits(256) !== f.E8M0_TRITS) p.push('E8M0_TRITS is not the fewest trits for 256 codes')
  if (trits(f.E4M3_POS_CODES) !== f.E4M3_POS_TRITS) p.push('E4M3_POS_TRITS is not the fewest trits for 127 codes')
  if (trits(32) !== f.INDEX32_TRITS || trits(32) !== f.E2M2_ELEM_TRITS) p.push('32 codes do not take 4 trits')
  if (f.BITS_T27_DENSE !== Math.ceil(f.BLOCK * f.CELL_TRITS * Math.log2(3)) + 8) p.push('BITS_T27_DENSE != ceil(96 log2 3) + 8')
  // positive finite E4M3 codes: exponent 0..15, mantissa 0..7, minus 0 and the NaN code
  if (f.E4M3_POS_CODES !== 16 * 8 - 1) p.push('E4M3_POS_CODES != 127')
  if (f.E4M3_MAX !== (1 + 6 / 8) * 2 ** (15 - 7)) p.push('E4M3_MAX is not the largest finite E4M3')
  if (!f.LADDER_COMPARATORS.includes(f.PRIMARY)) p.push('PRIMARY is not a ladder comparator')
  const path = join(REPO, f.BLOCK_TNF_FILE)
  if (!existsSync(path)) p.push(`${f.BLOCK_TNF_FILE} missing`)
  else if (sha256(readFileSync(path)) !== f.BLOCK_TNF_SHA256) p.push(`${f.BLOCK_TNF_FILE}: sha256 differs from the spec`)
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
    `# GENERATED by conformance/ternary_storage_v2_from_spec.mjs from ${SPEC} -- do not edit.`,
    '"""Ternary-storage search v2 parameters; the spec is the source, this file is a copy of it."""',
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
    let v1 = {}
    try {
      const v1Analysis = analyze(readFileSync(join(REPO, f.V1_SPEC), 'utf8'))
      v1 = Object.fromEntries(Object.entries(h.constsOf(v1Analysis)).map(([k, v]) => [k, v.value]))
    } catch (e) {
      problems.push(`first attempt's spec: ${e.message}`)
    }
    problems.push(...semanticProblems(f, v1))
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
