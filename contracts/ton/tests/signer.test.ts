import { beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { Blockchain, type SandboxContract, type TreasuryContract } from '@ton/sandbox'
import { Address, Cell, toNano, type Transaction } from '@ton/core'
import { keyPairFromSeed, sign, signVerify, type KeyPair } from '@ton/crypto'
import {
  attestationDigest,
  compileMinter,
  compileWallet,
  Err,
  offchainContent,
  TriMinter,
  type Attestation,
} from '../wrappers/TriMinter'
import { attest, nonceOf, workIdOf, type QueenLookup, type Signed, type SignerConfig, type Sources } from '../signer/attest'

/**
 * The signer's checks, each one refused in isolation, then the whole path: two
 * independent signers attest the same earning, their signatures mint in a TON
 * VM, and a rebound wallet cannot mint the same earning twice.
 */

const key = (i: number): KeyPair => {
  const seed = Buffer.alloc(32)
  seed[0] = i + 1
  return keyPairFromSeed(seed)
}
const KEYS = [0, 1, 2].map(key)

// A real accepted spec: gHashTag/t27 issue 5429, judged commit 7808383a, squash-merged as PR #5433.
const REPO = 'gHashTag/t27'
const ISSUE = 5429
const COMMIT = '7808383a3ca84c8a7ec813ae0869d8f3f7dc6309'
const SPEC = 'specs/port/trios/crates/trios-rainbow-bridge/src/lamport.t27'
const WORK_ID = workIdOf(REPO, ISSUE, COMMIT)
const PAYEE = `0:${'ab'.repeat(32)}`

const cfgAt = (i: number): SignerConfig => ({
  index: i,
  secretKey: KEYS[i].secretKey,
  publicKey: KEYS[i].publicKey,
  network: '-3',
  triPerSpec: 27,
})

const lookup = (over: Partial<QueenLookup['earning']> = {}, earner: Partial<QueenLookup['earner']> = {}): QueenLookup => ({
  scheme: 't27-accept:v1',
  triPerSpec: 27,
  earning: { workId: WORK_ID, repo: REPO, issue: ISSUE, commit: COMMIT, specPaths: [SPEC], revokedAt: null, ...over },
  earner: { name: '@gHashTag', claimed: true, github: 'gHashTag', ...earner },
})

/** Sources that answer as the live ones did for issue 5429, unless overridden. */
function fake(over: Partial<Sources> = {}, chain: { epoch?: number; spent?: Set<bigint> } = {}): Sources {
  return {
    queen: async id => (id === WORK_ID ? lookup() : null),
    defaultBranch: async () => 'master',
    pullsOfCommit: async () => [{ number: 5433, merged_at: '2026-09-30T10:00:00Z', base: { ref: 'master' } }],
    pullFiles: async () => [SPEC, 'docs/notes.md'],
    payee: async () => PAYEE,
    minter: async () => ({
      epoch: chain.epoch ?? 1,
      keyAt: async i => KEYS[i]?.publicKey ?? null,
      isSpent: async n => chain.spent?.has(n) ?? false,
    }),
    ...over,
  }
}

const refusal = async (src: Sources, id = WORK_ID, cfg = cfgAt(0)) => {
  const r = await attest(id, cfg, src)
  return r.ok ? 'signed' : r.code
}

describe('what one signer checks before it signs', () => {
  it('the work id is the Queen hash of a real accepted spec', () => {
    expect(WORK_ID).toMatch(/^[0-9a-f]{64}$/)
    // One earning, one nonce: the nonce does not depend on who is paid.
    expect(nonceOf(WORK_ID)).toBe(nonceOf(WORK_ID))
    expect(nonceOf(WORK_ID)).toBeLessThan(1n << 128n)
    expect(nonceOf(WORK_ID)).not.toBe(nonceOf(workIdOf(REPO, ISSUE + 1, COMMIT)))
  })

  it('signs the 27 TRI earning to the bound wallet, verifiably', async () => {
    const r = (await attest(WORK_ID, cfgAt(1), fake())) as Signed
    expect(r.ok).toBe(true)
    expect(r.index).toBe(1)
    expect(r.attestation).toEqual({
      worker: 'ab'.repeat(32),
      workId: WORK_ID,
      chain: 1,
      amountMtri: '27000',
      globalNonce: nonceOf(WORK_ID).toString(),
      epoch: 1,
    })
    expect(signVerify(Buffer.from(r.digest, 'hex'), Buffer.from(r.signature, 'hex'), KEYS[1].publicKey)).toBe(true)
  })

  it('refuses a malformed or unknown work id', async () => {
    expect(await refusal(fake(), 'nope')).toBe('work_id_malformed')
    expect(await refusal(fake(), 'f'.repeat(64))).toBe('earning_unknown')
  })

  it('refuses an earning whose fields do not hash to its id', async () => {
    expect(await refusal(fake({ queen: async () => lookup({ issue: ISSUE + 1 }) }))).toBe('earning_id_mismatch')
  })

  it('refuses a revoked earning, one with no .t27 file, and an unclaimed earner', async () => {
    expect(await refusal(fake({ queen: async () => lookup({ revokedAt: '2026-10-01T00:00:00Z' }) }))).toBe(
      'earning_revoked',
    )
    expect(await refusal(fake({ queen: async () => lookup({ specPaths: ['README.md'] }) }))).toBe('no_spec_declared')
    expect(await refusal(fake({ queen: async () => lookup({}, { claimed: false, github: undefined }) }))).toBe(
      'earner_unclaimed',
    )
  })

  it('refuses when Queen publishes a different amount than the signer signs for', async () => {
    expect(await refusal(fake({ queen: async () => ({ ...lookup(), triPerSpec: 81 }) }))).toBe('amount_mismatch')
  })

  it('O4: refuses a commit in no merged pull, or merged elsewhere than the default branch', async () => {
    expect(await refusal(fake({ pullsOfCommit: async () => [] }))).toBe('not_merged')
    expect(
      await refusal(fake({ pullsOfCommit: async () => [{ number: 1, merged_at: null, base: { ref: 'master' } }] })),
    ).toBe('not_merged')
    expect(
      await refusal(
        fake({ pullsOfCommit: async () => [{ number: 1, merged_at: '2026-09-30T10:00:00Z', base: { ref: 'dev' } }] }),
      ),
    ).toBe('not_merged')
  })

  it('O4: refuses a merged pull that did not carry the declared spec', async () => {
    expect(await refusal(fake({ pullFiles: async () => ['docs/notes.md'] }))).toBe('spec_not_in_merged_pull')
  })

  it('refuses an unbound or non-basechain payee', async () => {
    expect(await refusal(fake({ payee: async () => null }))).toBe('payee_unbound')
    expect(await refusal(fake({ payee: async () => 'garbage' }))).toBe('payee_malformed')
    expect(await refusal(fake({ payee: async () => `-1:${'ab'.repeat(32)}` }))).toBe('payee_malformed')
  })

  it('refuses when its key is not the one the minter holds at its index', async () => {
    expect(await refusal(fake(), WORK_ID, { ...cfgAt(0), index: 2 })).toBe('key_not_in_set')
  })

  it('refuses an earning whose nonce the minter already spent', async () => {
    expect(await refusal(fake({}, { spent: new Set([nonceOf(WORK_ID)]) }))).toBe('already_minted')
  })
})

function exitOn(txs: Transaction[], at: Address): number | undefined {
  for (const tx of txs) {
    const dest = tx.inMessage?.info.dest
    if (!dest || !Address.isAddress(dest) || !dest.equals(at)) continue
    const d = tx.description
    if (d.type !== 'generic' || d.computePhase.type !== 'vm') return undefined
    return d.computePhase.exitCode
  }
  return undefined
}

describe('two signers, one quorum, one mint -- in the TON VM', () => {
  let minterCode: Cell
  let walletCode: Cell
  let chain: Blockchain
  let payer: SandboxContract<TreasuryContract>
  let minter: SandboxContract<TriMinter>

  beforeAll(async () => {
    minterCode = await compileMinter()
    walletCode = await compileWallet()
  })

  beforeEach(async () => {
    chain = await Blockchain.create()
    payer = await chain.treasury('payer')
    minter = chain.openContract(
      TriMinter.createFromConfig(
        {
          attestors: KEYS.map(k => k.publicKey),
          threshold: 2,
          epoch: 1,
          content: offchainContent('https://t27.ai/tri/jetton.json'),
          walletCode,
        },
        minterCode,
      ),
    )
    await minter.sendDeploy(payer.getSender(), toNano('1'))
  })

  /** The real sources, except that the chain is this sandbox. */
  const onSandbox = (payee: string): Sources =>
    fake({
      payee: async () => payee,
      minter: async () => ({
        epoch: (await minter.getTriState()).epoch,
        keyAt: i => minter.getAttestorKey(i),
        isSpent: n => minter.getIsSpent(n),
      }),
    })

  const toAtt = (s: Signed): Attestation => ({
    worker: Buffer.from(s.attestation.worker, 'hex'),
    workId: Buffer.from(s.attestation.workId, 'hex'),
    chain: s.attestation.chain,
    amountMtri: BigInt(s.attestation.amountMtri),
    globalNonce: BigInt(s.attestation.globalNonce),
    epoch: s.attestation.epoch,
  })

  const quorum = async (payee: string) => {
    const a = (await attest(WORK_ID, cfgAt(0), onSandbox(payee))) as Signed
    const b = (await attest(WORK_ID, cfgAt(2), onSandbox(payee))) as Signed
    expect(a.ok && b.ok).toBe(true)
    // Independent signers, same facts, same bytes.
    expect(a.digest).toBe(b.digest)
    expect(attestationDigest(toAtt(a)).toString('hex')).toBe(a.digest)
    return {
      att: toAtt(a),
      sigs: new Map([
        [a.index, Buffer.from(a.signature, 'hex')],
        [b.index, Buffer.from(b.signature, 'hex')],
      ]),
    }
  }

  const balanceOf = async (owner: Address) => {
    const acc = await chain.getContract(await minter.getWalletAddress(owner))
    if (acc.accountState?.type !== 'active') return 0n
    return (await acc.get('get_wallet_data')).stackReader.readBigNumber()
  }

  it('the minter reads back the attestor keys it was deployed with', async () => {
    expect((await minter.getAttestorKey(1))?.equals(KEYS[1].publicKey)).toBe(true)
    expect(await minter.getAttestorKey(7)).toBeNull()
  })

  it('mints 27 TRI to the bound wallet, and the same earning never mints again', async () => {
    const { att, sigs } = await quorum(PAYEE)
    const r = await minter.sendMintOnAtt(payer.getSender(), { att, sigs })
    expect(exitOn(r.transactions, minter.address)).toBe(0)
    expect(await balanceOf(Address.parseRaw(PAYEE))).toBe(27_000n)
    expect((await minter.getTriState()).mintedTotal).toBe(27_000n)

    // Signers now refuse on their own: the nonce is spent.
    expect(await refusal(onSandbox(PAYEE))).toBe('already_minted')

    // A payee who rebinds a new wallet cannot mint the same earning twice:
    // the nonce is the earning's, not the wallet's, and the minter refuses it.
    const other = `0:${'cd'.repeat(32)}`
    const replay: Attestation = { ...att, worker: Buffer.from('cd'.repeat(32), 'hex') }
    const d = attestationDigest(replay)
    const r2 = await minter.sendMintOnAtt(payer.getSender(), {
      att: replay,
      sigs: new Map([
        [0, sign(d, KEYS[0].secretKey)],
        [2, sign(d, KEYS[2].secretKey)],
      ]),
    })
    expect(exitOn(r2.transactions, minter.address)).toBe(Err.replayed)
    expect(await balanceOf(Address.parseRaw(other))).toBe(0n)
  })
})
