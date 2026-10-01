import { Address } from '@ton/core'
import type { TonClient } from '@ton/ton'
import { TriMinter } from '../wrappers/TriMinter'
import type { Network, QueenLookup, Sources } from './attest'

/**
 * The live sources one signer reads: Queen, GitHub and the payee record over
 * HTTPS, the minter over a TON RPC. Every call goes from this signer's own
 * process; nothing is taken from the request that asked for the signature.
 */

export interface LiveConfig {
  queenUrl: string
  payeeUrl: string
  githubToken?: string
  minter: Address
  client: TonClient
  /** Retries toncenter 429/503/504; identity when the caller has its own. */
  rpc?: <T>(f: () => Promise<T>) => Promise<T>
  fetch?: typeof fetch
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

/** toncenter without a key allows ~1 request/s; retry throttling instead of failing. */
export async function retrying<T>(f: () => Promise<T>): Promise<T> {
  for (let i = 0; ; i++) {
    try {
      return await f()
    } catch (e) {
      const status = (e as { response?: { status?: number } }).response?.status
      if (i < 8 && (status === 429 || status === 503 || status === 504)) {
        await sleep(1500 * (i + 1))
        continue
      }
      throw e
    }
  }
}

export function liveSources(cfg: LiveConfig): Sources {
  const f = cfg.fetch ?? fetch
  const rpc = cfg.rpc ?? retrying
  const strip = (u: string) => u.replace(/\/+$/, '')

  async function json<T>(url: string, init?: RequestInit, missing = false): Promise<T | null> {
    const r = await f(url, init)
    if (missing && r.status === 404) return null
    if (!r.ok) throw new Error(`${url} -> ${r.status}`)
    return (await r.json()) as T
  }

  const gh = (path: string) =>
    json<unknown>(`https://api.github.com${path}`, {
      headers: {
        accept: 'application/vnd.github+json',
        'x-github-api-version': '2022-11-28',
        ...(cfg.githubToken ? { authorization: `Bearer ${cfg.githubToken}` } : {}),
      },
    })

  const minter = cfg.client.open(new TriMinter(cfg.minter))

  return {
    queen: workId =>
      json<QueenLookup>(`${strip(cfg.queenUrl)}/queen/public-earnings/${workId}`, undefined, true),

    async pullsOfCommit(repo, commit) {
      return (await gh(`/repos/${repo}/commits/${commit}/pulls?per_page=100`)) as Array<{
        number: number
        merged_at: string | null
        base: { ref: string }
      }>
    },

    async defaultBranch(repo) {
      return ((await gh(`/repos/${repo}`)) as { default_branch: string }).default_branch
    },

    async pullFiles(repo, pull) {
      // 3000 files is GitHub's own ceiling for this listing; a spec pull is far smaller.
      const out: string[] = []
      for (let page = 1; page <= 30; page++) {
        const batch = (await gh(`/repos/${repo}/pulls/${pull}/files?per_page=100&page=${page}`)) as Array<{
          filename: string
        }>
        out.push(...batch.map(x => x.filename))
        if (batch.length < 100) break
      }
      return out
    },

    async payee(github: string, network: Network) {
      const q = new URLSearchParams({ github, network })
      const r = await json<{ address: string | null }>(`${strip(cfg.payeeUrl)}/api/tri/payee?${q}`, undefined, true)
      return r?.address ?? null
    },

    async minter() {
      const s = await rpc(() => minter.getTriState())
      return {
        epoch: s.epoch,
        keyAt: (index: number) => rpc(() => minter.getAttestorKey(index)),
        isSpent: (nonce: bigint) => rpc(() => minter.getIsSpent(nonce)),
      }
    },
  }
}
