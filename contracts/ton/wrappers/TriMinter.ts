import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compileFunc } from '@ton-community/func-js'
import {
  Address,
  beginCell,
  Cell,
  contractAddress,
  Dictionary,
  SendMode,
  type Contract,
  type ContractProvider,
  type Sender,
} from '@ton/core'
import { sha256_sync } from '@ton/crypto'

/**
 * The TRI minter (contracts/ton/tri_minter.fc) and the reference jetton wallet
 * it deploys, as the sandbox tests and the deploy script use them.
 *
 * Every layout here mirrors src/trinet/mint_authority.zig: `attestationDigest`
 * is the oracle's `Attestation.digest`, `rotationDigest` its `rotationDigest`.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
export const TON_DIR = join(HERE, '..')
const VENDOR = 'vendor/token-contract'

export const CAP_MTRI = 10_460_353_203_000n // 3^21 TRI * 1000
export const CHAIN_TON = 1
export const CHAIN_SOLANA = 2
export const OP_MINT_ON_ATT = 0x54524931 // "TRI1"
export const OP_ROTATE = 0x54524952 // "TRIR"
export const MIN_MINT_VALUE = 50_000_000n // 0.05 TON

export const Err = {
  zeroAmount: 101,
  wrongChain: 102,
  wrongEpoch: 103,
  replayed: 104,
  subQuorum: 105,
  overCap: 106,
  lowValue: 107,
  badAttestors: 108,
  notWallet: 109,
  unknownOp: 0xffff,
} as const

async function compile(targets: string[]): Promise<Cell> {
  const r = await compileFunc({
    targets,
    sources: (path: string) => readFileSync(join(TON_DIR, path), 'utf8'),
  })
  if (r.status === 'error') throw new Error(r.message)
  return Cell.fromBase64(r.codeBoc)
}

/** The minter's code. Its #includes pull the vendored stdlib and helpers. */
export const compileMinter = () => compile(['tri_minter.fc'])

/** The reference wallet has no #includes; upstream's compile.sh concatenates. */
export const compileWallet = () =>
  compile(
    ['stdlib.fc', 'params.fc', 'op-codes.fc', 'jetton-utils.fc', 'jetton-wallet.fc'].map(
      f => `${VENDOR}/${f}`,
    ),
  )

/** TEP-64 off-chain content: 0x01 ++ URL. */
export function offchainContent(url: string): Cell {
  return beginCell().storeUint(1, 8).storeStringTail(url).endCell()
}

export type Attestation = {
  worker: Buffer // 32 bytes: the account id of a workchain-0 address
  workId: Buffer // 32 bytes
  chain: number
  amountMtri: bigint
  globalNonce: bigint
  epoch: number
}

/** mint_authority.zig `Attestation.digest`: sha256 of the 93-byte big-endian layout. */
export function attestationDigest(a: Attestation): Buffer {
  const b = Buffer.alloc(93)
  a.worker.copy(b, 0)
  a.workId.copy(b, 32)
  b.writeUInt8(a.chain, 64)
  b.writeBigUInt64BE(a.amountMtri, 65)
  b.writeBigUInt64BE(a.globalNonce >> 64n, 73)
  b.writeBigUInt64BE(a.globalNonce & 0xffff_ffff_ffff_ffffn, 81)
  b.writeUInt32BE(a.epoch, 89)
  return sha256_sync(b)
}

/** mint_authority.zig `rotationDigest`. `minter` is the minter's account id. */
export function rotationDigest(
  minter: Buffer,
  newEpoch: number,
  threshold: number,
  keys: Buffer[],
): Buffer {
  let h: Buffer = Buffer.alloc(32)
  for (const k of keys) h = sha256_sync(Buffer.concat([h, k]))
  const b = Buffer.alloc(74)
  b.write('TRIR', 0, 'ascii')
  minter.copy(b, 4)
  b.writeUInt32BE(newEpoch, 36)
  b.writeUInt8(threshold, 40)
  b.writeUInt8(keys.length, 41)
  h.copy(b, 42)
  return sha256_sync(b)
}

/** Signatures keyed by attestor index, as the contract counts them. */
export function sigDict(sigs: Map<number, Buffer>) {
  const d = Dictionary.empty(Dictionary.Keys.Uint(8), Dictionary.Values.Buffer(64))
  for (const [i, s] of sigs) d.set(i, s)
  return d
}

export function attestorCell(keys: Buffer[]): Cell {
  const d = Dictionary.empty(Dictionary.Keys.Uint(8), Dictionary.Values.BigUint(256))
  keys.forEach((k, i) => d.set(i, BigInt('0x' + k.toString('hex'))))
  return beginCell().storeDictDirect(d).endCell()
}

/** The `op::mint_on_att` message body. */
export function mintBody(opts: { att: Attestation; sigs: Map<number, Buffer>; queryId?: bigint }): Cell {
  const a = opts.att
  return beginCell()
    .storeUint(OP_MINT_ON_ATT, 32)
    .storeUint(opts.queryId ?? 0n, 64)
    .storeBuffer(a.worker, 32)
    .storeBuffer(a.workId, 32)
    .storeUint(a.chain, 8)
    .storeUint(a.amountMtri, 64)
    .storeUint(a.globalNonce, 128)
    .storeUint(a.epoch, 32)
    .storeDict(sigDict(opts.sigs))
    .endCell()
}

export type TriMinterConfig = {
  attestors: Buffer[]
  threshold: number
  epoch: number
  content: Cell
  walletCode: Cell
  /** TESTS ONLY: a deploy starts at zero. Lets a test stand next to the cap. */
  mintedTotal?: bigint
}

export function triMinterData(c: TriMinterConfig): Cell {
  if (c.attestors.length < 1 || c.attestors.length > 255) throw new Error('1..255 attestors')
  if (c.threshold < 1 || c.threshold > c.attestors.length) throw new Error('1 <= M <= N')
  return beginCell()
    .storeCoins(0) // total_supply: genesis is zero
    .storeUint(c.mintedTotal ?? 0n, 64)
    .storeUint(c.epoch, 32)
    .storeUint(c.threshold, 8)
    .storeUint(c.attestors.length, 8)
    .storeRef(attestorCell(c.attestors))
    .storeDict(null) // spent: empty
    .storeRef(c.content)
    .storeRef(c.walletCode)
    .endCell()
}

export class TriMinter implements Contract {
  constructor(
    readonly address: Address,
    readonly init?: { code: Cell; data: Cell },
  ) {}

  static createFromConfig(config: TriMinterConfig, code: Cell, workchain = 0) {
    const init = { code, data: triMinterData(config) }
    return new TriMinter(contractAddress(workchain, init), init)
  }

  async sendDeploy(provider: ContractProvider, via: Sender, value: bigint) {
    await provider.internal(via, { value, sendMode: SendMode.PAY_GAS_SEPARATELY, body: Cell.EMPTY })
  }

  async sendMintOnAtt(
    provider: ContractProvider,
    via: Sender,
    opts: { att: Attestation; sigs: Map<number, Buffer>; value?: bigint; queryId?: bigint },
  ) {
    await provider.internal(via, {
      value: opts.value ?? 100_000_000n,
      sendMode: SendMode.PAY_GAS_SEPARATELY,
      body: mintBody(opts),
    })
  }

  async sendRotate(
    provider: ContractProvider,
    via: Sender,
    opts: {
      newEpoch: number
      threshold: number
      keys: Buffer[]
      sigs: Map<number, Buffer>
      value?: bigint
    },
  ) {
    await provider.internal(via, {
      value: opts.value ?? 50_000_000n,
      sendMode: SendMode.PAY_GAS_SEPARATELY,
      body: beginCell()
        .storeUint(OP_ROTATE, 32)
        .storeUint(0, 64)
        .storeUint(opts.newEpoch, 32)
        .storeUint(opts.threshold, 8)
        .storeUint(opts.keys.length, 8)
        .storeRef(attestorCell(opts.keys))
        .storeDict(sigDict(opts.sigs))
        .endCell(),
    })
  }

  async getJettonData(provider: ContractProvider) {
    const r = (await provider.get('get_jetton_data', [])).stack
    return {
      totalSupply: r.readBigNumber(),
      mintable: r.readBoolean(),
      admin: r.readAddressOpt(),
      content: r.readCell(),
      walletCode: r.readCell(),
    }
  }

  async getWalletAddress(provider: ContractProvider, owner: Address) {
    const r = await provider.get('get_wallet_address', [
      { type: 'slice', cell: beginCell().storeAddress(owner).endCell() },
    ])
    return r.stack.readAddress()
  }

  async getTriState(provider: ContractProvider) {
    const r = (await provider.get('get_tri_state', [])).stack
    return {
      mintedTotal: r.readBigNumber(),
      cap: r.readBigNumber(),
      epoch: r.readNumber(),
      threshold: r.readNumber(),
      attestors: r.readNumber(),
    }
  }

  async getIsSpent(provider: ContractProvider, nonce: bigint) {
    const r = await provider.get('is_spent', [{ type: 'int', value: nonce }])
    return r.stack.readBoolean()
  }

  /** The ed25519 key the minter holds at `index`, or null when the slot is empty. */
  async getAttestorKey(provider: ContractProvider, index: number) {
    const r = await provider.get('attestor_key', [{ type: 'int', value: BigInt(index) }])
    const k = r.stack.readBigNumber()
    return k === 0n ? null : Buffer.from(k.toString(16).padStart(64, '0'), 'hex')
  }
}

/** The worker an attestation pays, as the TON address it mints to. */
export const workerAddress = (worker: Buffer) => new Address(0, worker)
