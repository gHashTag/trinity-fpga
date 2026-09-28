#!/usr/bin/env node
// e3_rx_capture_from_spec.mjs -- the E3 RX capture check's parameters, generated from its spec.
//
//   node conformance/e3_rx_capture_from_spec.mjs            write the generated file
//   node conformance/e3_rx_capture_from_spec.mjs --check    exit 1 if it drifted
//
// Source: specs/trinet/e3_rx_capture_model_ax7203.t27. Compiled by the t27 compiler (wasm), its test
// blocks evaluated against its constants, as conformance/e3_tx_hold_from_spec.mjs does; the compiler
// and the AST helpers are imported from a gHashTag/trinity checkout (TRINITY_DIR, default ~/trinity),
// not copied.
//
// Output (path from the spec's GENERATED): conformance/e3_rx_capture_params.py, a SPEC dict the
// runner conformance/e3_rx_capture_model.py reads.

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { homedir } from 'node:os'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SPEC = 'specs/trinet/e3_rx_capture_model_ax7203.t27'
const EXPECTED_MODULE = 'trinet_e3_rx_capture_model_ax7203'
const TRINITY = process.env.TRINITY_DIR ?? join(homedir(), 'trinity')
const SITE = join(TRINITY, 'apps', 'website')
const WASM = join(SITE, 'public', 't27', 't27_compiler.wasm')

const sha256 = (b) => createHash('sha256').update(b).digest('hex')
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

async function helpers() {
  for (const p of [WASM, join(SITE, 'scripts', 'agents-from-specs.mjs')]) {
    if (!existsSync(p)) throw new Error(`${p} not found; set TRINITY_DIR to a gHashTag/trinity checkout`)
  }
  const a = await import(pathToFileURL(join(SITE, 'scripts', 'agents-from-specs.mjs')).href)
  const v = await import(pathToFileURL(join(SITE, 'scripts', 'viewport-from-spec.mjs')).href)
  return { ...a, runSpecTests: v.runSpecTests }
}

// Relations the test evaluator cannot state (no file reads). Every constant this spec repeats is read
// back out of the file it came from: the E3 spec, the TX model's spec and log, the RTL and the XDC.
// The files under /tmp are the runner's to check (they live outside the repo).
function semanticProblems(f) {
  const p = []
  const where = (file) => join(REPO, file)
  const text = (file) => (existsSync(where(file)) ? readFileSync(where(file), 'utf8') : '')
  for (const [file, sha] of [[f.E3_SPEC_FILE, f.E3_SPEC_SHA256], [f.RTL_FILE, f.RTL_SHA256], [f.XDC_FILE, f.XDC_SHA256],
    [f.TX_SPEC_FILE, f.TX_SPEC_SHA256], [f.TX_RUNNER_FILE, f.TX_RUNNER_SHA256], [f.TX_LOG_FILE, f.TX_LOG_SHA256],
    [f.RUNNER, f.RUNNER_SHA256]]) {
    if (!existsSync(where(file))) p.push(`${file} missing`)
    else if (sha256(readFileSync(where(file))) !== sha) p.push(`${file}: sha256 differs from the spec`)
  }
  const e3 = text(f.E3_SPEC_FILE)
  if (!e3.includes(`pub const RTL_SHA256 : str = "${f.RTL_SHA256}";`)) p.push(`RTL_SHA256 differs from ${f.E3_SPEC_FILE}`)
  if (!e3.includes(`pub const RTL_FILE : str = "${f.RTL_FILE}";`)) p.push(`RTL_FILE differs from ${f.E3_SPEC_FILE}`)
  // the TX model's spec: same design files, and the /tmp files are its WORK_DIR's
  const tx = text(f.TX_SPEC_FILE)
  for (const k of ['E3_SPEC_SHA256', 'RTL_SHA256', 'XDC_SHA256', 'FASM_SHA256', 'RUNNER_SHA256']) {
    const mine = k === 'RUNNER_SHA256' ? f.TX_RUNNER_SHA256 : f[k]
    if (!tx.includes(`pub const ${k} : str = "${mine}";`)) p.push(`${k} differs from ${f.TX_SPEC_FILE}`)
  }
  if (!tx.includes(`pub const RUNNER : str = "${f.TX_RUNNER_FILE}";`)) p.push(`TX_RUNNER_FILE is not ${f.TX_SPEC_FILE}'s RUNNER`)
  const wd = tx.match(/^pub const WORK_DIR : str = "([^"]*)";/m)
  const work = wd ? wd[1] : '(none)'
  for (const [k, name] of [['SDF_FILE', 'e3z.sdf'], ['ROUTED_FILE', 'node_routed.json'], ['FASM_FILE', 'node.fasm']]) {
    if (f[k] !== `${work}/${name}`) p.push(`${k} ${f[k]} is not ${work}/${name}`)
  }
  // the TX model's one log: its run wrote these three files, and its FASM was e3z's
  const log = text(f.TX_LOG_FILE)
  if (!log.includes(`--write ${f.ROUTED_FILE} --fasm ${f.FASM_FILE} --sdf ${f.SDF_FILE} `)) p.push(`${f.TX_LOG_FILE}: no nextpnr run writing the three files`)
  if (!log.includes(`\nfasm: ${f.FASM_SHA256.slice(0, 16)} = e3z\n`)) p.push(`${f.TX_LOG_FILE}: FASM ${f.FASM_SHA256.slice(0, 16)} not recorded as e3z`)
  if (!log.includes(`\nsdf: ${f.SDF_FILE} ${f.SDF_SHA256.slice(0, 16)}, ${f.SDF_BYTES} bytes\n`)) p.push(`${f.TX_LOG_FILE}: SDF sha prefix or size differs`)
  // the RTL: the RXC buffer, the falling-edge pair, the rising-edge copy and the ed comparison
  const rtl = text(f.RTL_FILE)
  const rxd = f.DATA_PORTS[0].replace(/\[\d+\]$/, '')
  if (!f.DATA_PORTS.every((d, i) => d === `${rxd}[${i}]`)) p.push(`DATA_PORTS are not ${rxd}[0..${f.DATA_PORTS.length - 1}]`)
  if (!rtl.includes(`BUFG u_rxc_bufg (.I(${f.CLOCK_PORT}), .O(${f.RXC_NET}));`)) p.push(`${f.RXC_NET} is not ${f.CLOCK_PORT} through a BUFG in the RTL`)
  const fall = new RegExp(`always @\\(negedge ${esc(f.RXC_NET)}\\) begin\\s+${esc(f.MID_NET)}\\s+<= ${esc(rxd)};\\s+${esc(f.CTL_MID_NET)}\\s+<= ${esc(f.CTL_PORT)};\\s+end`)
  if (!fall.test(rtl)) p.push(`${f.MID_NET} and ${f.CTL_MID_NET} are not the falling-edge samples of ${rxd} and ${f.CTL_PORT} in the RTL`)
  if (!new RegExp(`^\\s+${esc(f.START_NET)}\\s+<= ${esc(rxd)};`, 'm').test(rtl)) p.push(`${f.START_NET} is not a direct sample of ${rxd} in the RTL`)
  if (!new RegExp(`^\\s+rd\\s+<= ${esc(f.MID_NET)};`, 'm').test(rtl)) p.push(`rd is not ${f.MID_NET} in the RTL`)
  if (!new RegExp(`^\\s+rdv\\s+<= ${esc(f.CTL_MID_NET)};`, 'm').test(rtl)) p.push(`rdv is not ${f.CTL_MID_NET} in the RTL`)
  if (!new RegExp(`^\\s+rxd_p2\\s+<= ${esc(f.START_NET)};`, 'm').test(rtl)) p.push(`rxd_p2 is not ${f.START_NET} in the RTL`)
  if (!rtl.includes('i_ed <= rdv && rdv_q && (rd != rxd_p2);')) p.push('ed is not the in-frame mismatch of rd and rxd_p2 in the RTL')
  // the XDC pads its columns with spaces: compare lines with runs of blanks folded to one
  const xdc = text(f.XDC_FILE).split('\n').map((l) => l.trim().replace(/\s+/g, ' '))
  for (const port of [...f.DATA_PORTS, f.CTL_PORT, f.CLOCK_PORT]) {
    if (!xdc.includes(`set_property IOSTANDARD LVCMOS33 [get_ports ${port}]`)) p.push(`${f.XDC_FILE}: no IOSTANDARD LVCMOS33 on ${port}`)
  }
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
    `# GENERATED by conformance/e3_rx_capture_from_spec.mjs from ${SPEC} -- do not edit.`,
    '"""E3 RX capture check parameters; the spec is the source, this file is a copy of it."""',
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
