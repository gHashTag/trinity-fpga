#!/usr/bin/env node
// eth_arp_icmp_e3_from_spec.mjs -- Ethernet step E3's board verdict parameters, generated from its spec.
//
//   node conformance/eth_arp_icmp_e3_from_spec.mjs            write the generated file
//   node conformance/eth_arp_icmp_e3_from_spec.mjs --check    exit 1 if it drifted
//
// Source: specs/trinet/eth_arp_icmp_e3_ax7203.t27. Compiled by the t27 compiler (wasm), its test
// blocks evaluated against its constants, as conformance/uart_loss_hubfree_from_spec.mjs does; the
// compiler and the AST helpers are imported from a gHashTag/trinity checkout (TRINITY_DIR,
// default ~/trinity), not copied.
//
// Output (path from the spec's GENERATED): conformance/eth_arp_icmp_e3_params.py, a SPEC dict that
// `conformance/eth_arp_icmp_ax7203.py --judge` reads.

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { homedir } from 'node:os'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SPEC = 'specs/trinet/eth_arp_icmp_e3_ax7203.t27'
const EXPECTED_MODULE = 'trinet_eth_arp_icmp_e3_ax7203'
const TRINITY = process.env.TRINITY_DIR ?? join(homedir(), 'trinity')
const SITE = join(TRINITY, 'apps', 'website')
const WASM = join(SITE, 'public', 't27', 't27_compiler.wasm')
const LOGS = ['LOG_PREPING', 'LOG_FLASH', 'LOG_BEFORE', 'LOG_PING', 'LOG_ARP', 'LOG_AFTER']

const sha256 = (b) => createHash('sha256').update(b).digest('hex')

async function helpers() {
  for (const p of [WASM, join(SITE, 'scripts', 'agents-from-specs.mjs')]) {
    if (!existsSync(p)) throw new Error(`${p} not found; set TRINITY_DIR to a gHashTag/trinity checkout`)
  }
  const a = await import(pathToFileURL(join(SITE, 'scripts', 'agents-from-specs.mjs')).href)
  const v = await import(pathToFileURL(join(SITE, 'scripts', 'viewport-from-spec.mjs')).href)
  return { ...a, runSpecTests: v.runSpecTests }
}

// Relations the test evaluator cannot state (no file reads, no exact division). Every constant the
// spec repeats is read back from the file it describes: the RTL's parameters, the checker's
// constants, the bitstream record, the E2z log. The pinned bytes make a later edit visible.
function semanticProblems(f) {
  const p = []
  const where = (file) => join(REPO, file)
  const text = (file) => (existsSync(where(file)) ? readFileSync(where(file), 'utf8') : '')
  const pins = [[f.RUNNER, f.RUNNER_SHA256]]
  for (const k of Object.keys(f).sort()) {
    if (!k.endsWith('_FILE')) continue
    const s = k.slice(0, -5) + '_SHA256'
    if (!(s in f)) p.push(`${k} has no ${s}`)
    else pins.push([f[k], f[s]])
  }
  for (const [file, sha] of pins) {
    if (!existsSync(where(file))) p.push(`${file} missing`)
    else if (sha256(readFileSync(where(file))) !== sha) p.push(`${file}: sha256 differs from the spec`)
  }
  if (!existsSync(where(f.RECORD_DOC))) p.push(`${f.RECORD_DOC} missing`)
  const names = LOGS.map((k) => f[k])
  if (new Set(names).size !== names.length || !names.every((n) => /^e3_[a-z_]+$/.test(n))) p.push(`log names ${names}`)

  const ipParts = f.IP_TEXT.split('.').map(Number)
  const ipOf = (a) => ((a[0] * 256 + a[1]) * 256 + a[2]) * 256 + a[3]
  if (ipParts.length !== 4 || ipOf(ipParts) !== f.IP_U32) p.push(`IP_TEXT ${f.IP_TEXT} != IP_U32 ${f.IP_U32}`)
  const mac = BigInt(f.MAC_HI16) * 2n ** 32n + BigInt(f.MAC_LO32)

  // the RTL's parameter defaults
  const rtl = text(f.RTL_FILE)
  const rp = (re) => rtl.match(re)?.[1] ?? null
  const rtlMac = rp(/parameter \[47:0\]\s+MAC\s+= 48'h([0-9A-Fa-f_]+)/)
  if (rtlMac === null || BigInt('0x' + rtlMac.replaceAll('_', '')) !== mac) p.push(`RTL MAC ${rtlMac} != spec`)
  const rtlIp = rtl.match(/parameter \[31:0\]\s+IP\s+= \{8'd(\d+), 8'd(\d+), 8'd(\d+), 8'd(\d+)\}/)
  if (!rtlIp || ipOf(rtlIp.slice(1).map(Number)) !== f.IP_U32) p.push('RTL IP != spec')
  if (Number(rp(/parameter \[7:0\]\s+TTL\s+= 8'd(\d+)/)) !== f.TTL) p.push('RTL TTL != spec')
  if (Number(rp(/parameter integer WIN_LOG2\s+= (\d+)/)) !== f.WIN_LOG2) p.push('RTL WIN_LOG2 != spec')
  if (Number(rp(/parameter integer POLL_LOG2\s+= (\d+)/)) !== f.POLL_LOG2) p.push('RTL POLL_LOG2 != spec')

  // the checker's constants
  const ck = text(f.RUNNER)
  const cp = (re) => ck.match(re)?.[1] ?? null
  const ckMac = cp(/^MAC = bytes\.fromhex\('([0-9A-Fa-f]{12})'\)$/m)
  if (ckMac === null || BigInt('0x' + ckMac) !== mac) p.push(`checker MAC ${ckMac} != spec`)
  const ckIp = ck.match(/^IP = bytes\(\[(\d+), (\d+), (\d+), (\d+)\]\)$/m)
  if (!ckIp || ipOf(ckIp.slice(1).map(Number)) !== f.IP_U32) p.push('checker IP != spec')
  if (Number(cp(/^TTL = (\d+)$/m)) !== f.TTL) p.push('checker TTL != spec')
  if (parseInt(cp(/^PHYID = 0x([0-9A-Fa-f]{8})$/m) ?? 'x', 16) !== f.PHY_ID) p.push('checker PHYID != spec')
  const mc = ck.match(/^CFGMCLK_HZ = \(([\d.]+)e6, ([\d.]+)e6\)/m)
  if (!mc || Math.round(Number(mc[1]) * 1e6) !== f.CFGMCLK_MIN_HZ || Math.round(Number(mc[2]) * 1e6) !== f.CFGMCLK_MAX_HZ) p.push('checker CFGMCLK_HZ != spec')
  const full = ck.match(/^FULL = dict\(([^)]*)\)/m)?.[1] ?? ''
  if (!full.includes(`WIN_LOG2=${f.WIN_LOG2},`) || !full.includes(`POLL_LOG2=${f.POLL_LOG2},`)) p.push('checker FULL WIN_LOG2/POLL_LOG2 != spec')
  if (!/while got < count and time\.time\(\) - t0 < count \* 1\.5 \+ 5:/.test(ck)) p.push('checker read timeout is no longer count * 1.5 + 5')

  // rc bounds, exact
  const W = 2n ** BigInt(f.WIN_LOG2)
  const lo = (BigInt(f.RXC_LO_HZ) * W) / BigInt(f.CFGMCLK_MAX_HZ) - 1n
  const hiNum = BigInt(f.RXC_HI_HZ) * W
  const hi = (hiNum + BigInt(f.CFGMCLK_MIN_HZ) - 1n) / BigInt(f.CFGMCLK_MIN_HZ) + 1n
  if (BigInt(f.RC_MIN) !== lo || BigInt(f.RC_MAX) !== hi) p.push(`RC_MIN/RC_MAX ${f.RC_MIN}/${f.RC_MAX} != ${lo}/${hi}`)
  if (f.RXC_LO_HZ !== f.RXC_HZ - f.RXC_HZ * f.RXC_PPM / 1e6 || f.RXC_HI_HZ !== f.RXC_HZ + f.RXC_HZ * f.RXC_PPM / 1e6) p.push('RXC_LO_HZ/RXC_HI_HZ')

  // the E2z report lines with ib=3B
  const rcs = [...text(f.E2Z_LOG_FILE).matchAll(/ ib=3B rc=([0-9A-F]{6}) /g)].map((m) => parseInt(m[1], 16))
  if (rcs.length !== f.E2Z_IB_LINES) p.push(`E2z ib=3B lines ${rcs.length} != E2Z_IB_LINES ${f.E2Z_IB_LINES}`)
  if (rcs.length && (Math.min(...rcs) !== f.E2Z_RC_MIN || Math.max(...rcs) !== f.E2Z_RC_MAX)) p.push(`E2z rc ${Math.min(...rcs)}..${Math.max(...rcs)} != spec`)
  if (f.IB !== 0x3b) p.push('IB is not 0x3B')

  // the bitstream record, and the .bit where it exists (it is not in git)
  const rec = text(f.BIT_RECORD_FILE).split('\n')
  if (rec[0] !== `${f.BIT_FILE_SHA256}  ${basename(f.BIT_NAME)} (file)`) p.push('bitstream record line 1 != BIT_FILE_SHA256')
  if (!(rec[1] ?? '').startsWith(`${f.PAYLOAD_SHA256}  payload from the sync word`)) p.push('bitstream record line 2 != PAYLOAD_SHA256')
  if (existsSync(where(f.BIT_NAME))) {
    const bit = readFileSync(where(f.BIT_NAME))
    const i = bit.indexOf(Buffer.from('aa995566', 'hex'))
    if (sha256(bit) !== f.BIT_FILE_SHA256) p.push(`${f.BIT_NAME}: sha256 != BIT_FILE_SHA256`)
    if (i < 0 || sha256(bit.subarray(i)) !== f.PAYLOAD_SHA256) p.push(`${f.BIT_NAME}: payload != PAYLOAD_SHA256`)
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
    `# GENERATED by conformance/eth_arp_icmp_e3_from_spec.mjs from ${SPEC} -- do not edit.`,
    '"""E3 board verdict parameters; the spec is the source, this file is a copy of it."""',
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
