import { createServer } from 'node:http'
import { readFileSync } from 'node:fs'
import { Address } from '@ton/core'
import { keyPairFromSecretKey } from '@ton/crypto'
import { TonClient } from '@ton/ton'
import { attest, type SignerConfig } from '../signer/attest'
import { liveSources } from '../signer/sources'

/**
 * ONE TRI attestor as a service. Run one per key holder, each on their own
 * machine with their own key; a claim needs M of them to agree.
 *
 *   POST /sign {"workId": "<64 hex>"}  -> 200 {ok, index, signature, digest, attestation}
 *                                      -> 422 {ok: false, code}  (a refusal, see signer/attest.ts)
 *   GET  /health                       -> {index, publicKey, minter, network}
 *
 * Environment:
 *   TRI_SIGNER_INDEX         this key's index in the minter's attestor set
 *   TRI_SIGNER_SECRET        64-byte ed25519 secret key, hex   (or:)
 *   TRI_SIGNER_SECRET_FILE   a JSON file {secretKeys: hex[]}, read at TRI_SIGNER_INDEX
 *   TRI_MINTER               the minter address
 *   QUEEN_URL                Queen, for the earning
 *   TRI_PAYEE_URL            the payee record (render), for the bound wallet
 *   GITHUB_TOKEN             optional; raises the GitHub rate limit
 *   TONCENTER_API_KEY        optional; raises the toncenter rate limit
 *   PORT                     default 8790
 *
 * TESTNET ONLY. The endpoint is fixed to testnet and the network to "-3": the
 * mint digest carries no deployment domain yet, so a key that signs here must
 * never sign for mainnet. V1, signer quorum, NOT trustless.
 */

const TRI_PER_SPEC = 27
const ENDPOINT = 'https://testnet.toncenter.com/api/v2/jsonRPC'

function need(name: string): string {
  const v = process.env[name]
  if (!v) throw new Error(`${name} is not set`)
  return v
}

const index = Number(need('TRI_SIGNER_INDEX'))
const secretHex = process.env.TRI_SIGNER_SECRET
  ? process.env.TRI_SIGNER_SECRET
  : (JSON.parse(readFileSync(need('TRI_SIGNER_SECRET_FILE'), 'utf8')) as { secretKeys: string[] }).secretKeys[index]
if (!secretHex || !/^[0-9a-f]{128}$/i.test(secretHex)) throw new Error('signer secret must be 64 bytes of hex')
const keys = keyPairFromSecretKey(Buffer.from(secretHex, 'hex'))

const cfg: SignerConfig = {
  index,
  secretKey: keys.secretKey,
  publicKey: keys.publicKey,
  network: '-3',
  triPerSpec: TRI_PER_SPEC,
}
const minter = Address.parse(need('TRI_MINTER'))
const sources = liveSources({
  queenUrl: need('QUEEN_URL'),
  payeeUrl: need('TRI_PAYEE_URL'),
  githubToken: process.env.GITHUB_TOKEN,
  minter,
  client: new TonClient({ endpoint: ENDPOINT, apiKey: process.env.TONCENTER_API_KEY }),
})

const send = (res: import('node:http').ServerResponse, status: number, body: unknown) => {
  res.writeHead(status, { 'content-type': 'application/json' })
  res.end(JSON.stringify(body))
}

const server = createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/health') {
      return send(res, 200, {
        index,
        publicKey: keys.publicKey.toString('hex'),
        minter: minter.toString({ testOnly: true }),
        network: cfg.network,
      })
    }
    if (req.method === 'POST' && req.url === '/sign') {
      let raw = ''
      for await (const chunk of req) {
        raw += chunk
        if (raw.length > 4096) return send(res, 413, { ok: false, code: 'body_too_large' })
      }
      let workId: unknown
      try {
        workId = (JSON.parse(raw) as { workId?: unknown }).workId
      } catch {
        return send(res, 400, { ok: false, code: 'body_not_json' })
      }
      const out = await attest(String(workId ?? ''), cfg, sources)
      console.log(JSON.stringify({ at: new Date().toISOString(), workId, ok: out.ok, code: out.ok ? null : out.code }))
      return send(res, out.ok ? 200 : 422, out)
    }
    send(res, 404, { ok: false, code: 'not_found' })
  } catch (e) {
    console.error('sign failed', e)
    send(res, 502, { ok: false, code: 'source_unavailable' })
  }
})

const port = Number(process.env.PORT ?? 8790)
server.listen(port, () => console.log(`tri signer #${index} on :${port}, key ${keys.publicKey.toString('hex').slice(0, 16)}…`))
