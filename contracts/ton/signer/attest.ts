import { createHash } from 'node:crypto'
import { Address } from '@ton/core'
import { sign } from '@ton/crypto'
import { attestationDigest, CHAIN_TON, type Attestation } from '../wrappers/TriMinter'

/**
 * ONE TRI SIGNER: what an attestor checks, by itself, before it signs a mint.
 *
 * A mint needs M of N attestor signatures over one attestation (worker, work
 * id, chain, amount, nonce, epoch). Each signer runs this on its own machine,
 * with its own key, and asks the public sources directly -- never the claim
 * API that forwarded the request. A claim API that lied about an earning would
 * therefore have to fool M independent signers reading Queen and GitHub
 * themselves. V1, signer quorum, NOT trustless: signers that collude, or a
 * payee record that lies to all of them, still mint wrongly.
 *
 * WHAT IS CHECKED, AND WHERE:
 *   1. Queen (/queen/public-earnings/<work id>): the earning exists, its id is
 *      the hash of its own public fields (recomputed here, not taken), it is
 *      not revoked, it declares a .t27 file, it is credited to a GitHub login,
 *      and the amount Queen publishes is the amount this signer was told.
 *   2. GitHub: decision O4 -- the judged commit is in a pull request MERGED
 *      into the repository's default branch, and that pull request changes a
 *      .t27 file the earning declared. The t27 repository squash-merges, so
 *      the judged commit itself is not an ancestor of the default branch.
 *   3. The payee record (/api/tri/payee): the TON wallet that GitHub login
 *      proved, with ton_proof, it controls.
 *   4. The minter: the epoch is the live one, this signer's key is the key the
 *      minter holds at this index, and the nonce is not spent yet.
 *
 * ONE EARNING, ONE NONCE. The minter refuses a spent nonce, not a seen work id,
 * so the nonce is derived from the work id alone. A payee who rebinds their
 * wallet after a mint gets a second attestation with a different worker and
 * the SAME nonce, which the minter refuses: one earning can mint once.
 */

export const EARNING_SCHEME = 't27-accept:v1'
export const NONCE_SCHEME = 't27-tri-nonce:v1'

export type Network = '-3' | '-239'

export interface QueenLookup {
  scheme: string
  triPerSpec: number
  earning: {
    workId: string
    repo: string
    issue: number
    commit: string
    specPaths: string[]
    revokedAt: string | null
  }
  earner: { name: string; claimed: boolean; github?: string }
}

/** What the signer reads from the outside world; injected so tests drive it. */
export interface Sources {
  queen(workId: string): Promise<QueenLookup | null>
  /** Pull requests GitHub associates with a commit. */
  pullsOfCommit(
    repo: string,
    commit: string,
  ): Promise<Array<{ number: number; merged_at: string | null; base: { ref: string } }>>
  defaultBranch(repo: string): Promise<string>
  pullFiles(repo: string, pull: number): Promise<string[]>
  /** The raw address ("0:<hex>") a GitHub login bound on `network`, or null. */
  payee(github: string, network: Network): Promise<string | null>
  minter(): Promise<{ epoch: number; keyAt(index: number): Promise<Buffer | null>; isSpent(nonce: bigint): Promise<boolean> }>
}

export interface SignerConfig {
  index: number
  secretKey: Buffer
  publicKey: Buffer
  network: Network
  /** TRI per accepted spec this signer will sign for, in whole TRI. */
  triPerSpec: number
}

export type Signed = {
  ok: true
  index: number
  signature: string
  digest: string
  attestation: {
    worker: string
    workId: string
    chain: number
    amountMtri: string
    globalNonce: string
    epoch: number
  }
}
export type Refused = { ok: false; code: string }

export function workIdOf(repo: string, issue: number, commit: string): string {
  return createHash('sha256').update(`${EARNING_SCHEME}|${repo}|${issue}|${commit}`).digest('hex')
}

/** uint128 from sha256(scheme|work id): one earning, one nonce, forever. */
export function nonceOf(workId: string): bigint {
  const h = createHash('sha256').update(`${NONCE_SCHEME}|${workId}`).digest('hex')
  return BigInt('0x' + h.slice(0, 32))
}

const WORK_ID = /^[0-9a-f]{64}$/

export async function attest(workId: string, cfg: SignerConfig, src: Sources): Promise<Signed | Refused> {
  if (!WORK_ID.test(workId)) return { ok: false, code: 'work_id_malformed' }

  // 1. Queen
  const q = await src.queen(workId)
  if (!q) return { ok: false, code: 'earning_unknown' }
  if (q.scheme !== EARNING_SCHEME) return { ok: false, code: 'scheme_unknown' }
  const e = q.earning
  if (workIdOf(e.repo, e.issue, e.commit) !== workId) return { ok: false, code: 'earning_id_mismatch' }
  if (e.revokedAt) return { ok: false, code: 'earning_revoked' }
  const specs = e.specPaths.filter(p => p.endsWith('.t27'))
  if (specs.length === 0) return { ok: false, code: 'no_spec_declared' }
  if (!q.earner.claimed || !q.earner.github) return { ok: false, code: 'earner_unclaimed' }
  if (q.triPerSpec !== cfg.triPerSpec) return { ok: false, code: 'amount_mismatch' }

  // 2. GitHub (O4)
  const base = await src.defaultBranch(e.repo)
  const merged = (await src.pullsOfCommit(e.repo, e.commit)).filter(
    p => p.merged_at !== null && p.base.ref === base,
  )
  if (merged.length === 0) return { ok: false, code: 'not_merged' }
  let landed = false
  for (const p of merged) {
    const files = new Set(await src.pullFiles(e.repo, p.number))
    if (specs.some(s => files.has(s))) {
      landed = true
      break
    }
  }
  if (!landed) return { ok: false, code: 'spec_not_in_merged_pull' }

  // 3. Payee
  const raw = await src.payee(q.earner.github, cfg.network)
  if (!raw) return { ok: false, code: 'payee_unbound' }
  let worker: Address
  try {
    worker = Address.parseRaw(raw)
  } catch {
    return { ok: false, code: 'payee_malformed' }
  }
  if (worker.workChain !== 0) return { ok: false, code: 'payee_malformed' }

  // 4. Minter
  const m = await src.minter()
  const onChain = await m.keyAt(cfg.index)
  if (!onChain || !onChain.equals(cfg.publicKey)) return { ok: false, code: 'key_not_in_set' }
  const nonce = nonceOf(workId)
  if (await m.isSpent(nonce)) return { ok: false, code: 'already_minted' }

  const att: Attestation = {
    worker: worker.hash,
    workId: Buffer.from(workId, 'hex'),
    chain: CHAIN_TON,
    amountMtri: BigInt(cfg.triPerSpec) * 1000n,
    globalNonce: nonce,
    epoch: m.epoch,
  }
  const digest = attestationDigest(att)
  return {
    ok: true,
    index: cfg.index,
    signature: sign(digest, cfg.secretKey).toString('hex'),
    digest: digest.toString('hex'),
    attestation: {
      worker: worker.hash.toString('hex'),
      workId,
      chain: att.chain,
      amountMtri: att.amountMtri.toString(),
      globalNonce: att.globalNonce.toString(),
      epoch: att.epoch,
    },
  }
}
