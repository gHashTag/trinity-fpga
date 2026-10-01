import { beginCell, contractAddress, storeStateInit, toNano } from '@ton/core'
import {
  compileMinter,
  compileWallet,
  offchainContent,
  triMinterData,
} from '../wrappers/TriMinter'

/**
 * Print a TESTNET deploy link for the TRI minter. Holds no key and sends
 * nothing: the operator opens the link in a testnet wallet and pays the deploy.
 *
 *   ATTESTORS=<hex pk>,<hex pk>,<hex pk> THRESHOLD=2 \
 *     npx tsx scripts/deploy-testnet.ts
 *
 * The attestor keys MUST be testnet-only. The mint digest carries no
 * deployment domain, so an attestation signed by keys that are also on a
 * mainnet minter replays there (contracts/README.md, "Known limits").
 *
 * Mainnet is not a flag here on purpose: a mainnet deploy is the owner's act,
 * after an audit, with keys held by separate owners.
 */

const keys = (process.env.ATTESTORS ?? '')
  .split(',')
  .map(s => s.trim())
  .filter(Boolean)
  .map(h => {
    if (!/^[0-9a-f]{64}$/i.test(h)) throw new Error(`not a 32-byte hex public key: ${h}`)
    return Buffer.from(h, 'hex')
  })
const threshold = Number(process.env.THRESHOLD ?? 0)
if (keys.length === 0 || !threshold) {
  console.error('set ATTESTORS (comma-separated hex ed25519 public keys) and THRESHOLD')
  process.exit(2)
}
if (new Set(keys.map(k => k.toString('hex'))).size !== keys.length) {
  throw new Error('duplicate attestor key: one owner would count twice')
}

const code = await compileMinter()
const data = triMinterData({
  attestors: keys,
  threshold,
  epoch: 1,
  content: offchainContent(process.env.CONTENT_URL ?? 'https://t27.ai/tri/jetton.json'),
  walletCode: await compileWallet(),
})
const init = { code, data }
const address = contractAddress(0, init)
const stateInit = beginCell().store(storeStateInit(init)).endCell().toBoc().toString('base64url')
const amount = toNano(process.env.AMOUNT ?? '0.5')

console.log(`minter (testnet): ${address.toString({ testOnly: true, bounceable: false })}`)
console.log(`code hash:        ${code.hash().toString('hex')}`)
console.log(`attestors:        ${threshold}-of-${keys.length}, epoch 1`)
console.log(
  `open in a TESTNET wallet:\n  ton://transfer/${address.toString({ testOnly: true, bounceable: false })}` +
    `?amount=${amount}&init=${stateInit}`,
)
