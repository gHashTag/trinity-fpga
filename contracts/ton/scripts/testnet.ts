import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { Address, fromNano, internal, SendMode, toNano, type Cell, type OpenedContract } from '@ton/core'
import {
  getSecureRandomBytes,
  keyPairFromSecretKey,
  keyPairFromSeed,
  mnemonicNew,
  mnemonicToPrivateKey,
  sign,
  type KeyPair,
} from '@ton/crypto'
import { TonClient, WalletContractV5R1 } from '@ton/ton'
import {
  attestationDigest,
  CHAIN_TON,
  compileMinter,
  compileWallet,
  offchainContent,
  TriMinter,
  mintBody,
  type Attestation,
} from '../wrappers/TriMinter'

/**
 * The TESTNET operator for the TRI minter. There is no network flag: the
 * endpoint below is testnet, and a mainnet deploy is the owner's act, after an
 * audit, with attestor keys held by separate owners.
 *
 *   npx tsx scripts/testnet.ts wallet        create or show the deployer wallet
 *   npx tsx scripts/testnet.ts attestors     create or show the testnet attestor set
 *   npx tsx scripts/testnet.ts deploy        deploy the minter (2-of-3) from the deployer
 *   npx tsx scripts/testnet.ts mint <addr> <mTRI>   quorum-sign and mint to a wc-0 address
 *   npx tsx scripts/testnet.ts status        minter supply, cap counter, epoch
 *
 * Keys live in ~/.tri-testnet (mode 0600), never in the repository. The
 * attestor keys are TESTNET-ONLY: the mint digest carries no deployment domain,
 * so a key reused on mainnet would let testnet attestations mint there. While
 * one operator holds all three, the testnet quorum is one party with three
 * keys -- a pipeline test, not a trust model.
 */

const ENDPOINT = 'https://testnet.toncenter.com/api/v2/jsonRPC'
const HOME = process.env.TRI_TESTNET_HOME ?? join(homedir(), '.tri-testnet')
const THRESHOLD = 2
const N_ATTESTORS = 3

const client = new TonClient({ endpoint: ENDPOINT, apiKey: process.env.TONCENTER_API_KEY })
const fmt = (a: Address) => a.toString({ testOnly: true, bounceable: false })
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

/** toncenter without a key allows ~1 request/s; retry 429s instead of failing. */
async function rpc<T>(f: () => Promise<T>): Promise<T> {
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

function secretFile<T>(name: string, create: () => Promise<T>): Promise<T> {
  const p = join(HOME, name)
  if (existsSync(p)) return Promise.resolve(JSON.parse(readFileSync(p, 'utf8')) as T)
  mkdirSync(HOME, { recursive: true, mode: 0o700 })
  return create().then(v => {
    writeFileSync(p, JSON.stringify(v, null, 2) + '\n', { mode: 0o600 })
    chmodSync(p, 0o600)
    return v
  })
}

async function deployer() {
  const { mnemonic } = await secretFile('deployer.json', async () => ({
    network: 'testnet',
    wallet: 'v5r1',
    mnemonic: await mnemonicNew(24),
  }))
  const key = await mnemonicToPrivateKey(mnemonic)
  const wallet = client.open(
    WalletContractV5R1.create({ workchain: 0, publicKey: key.publicKey, walletId: { networkGlobalId: -3 } }),
  )
  return { key, wallet }
}

async function attestors(): Promise<KeyPair[]> {
  const { secretKeys } = await secretFile('attestors.json', async () => ({
    network: 'testnet',
    note: 'TESTNET-ONLY attestor keys. Never reuse on a mainnet minter.',
    secretKeys: await Promise.all(
      Array.from({ length: N_ATTESTORS }, async () =>
        keyPairFromSeed(await getSecureRandomBytes(32)).secretKey.toString('hex'),
      ),
    ),
  }))
  return secretKeys.map(h => keyPairFromSecretKey(Buffer.from(h, 'hex')))
}

async function minterContract(): Promise<OpenedContract<TriMinter>> {
  const keys = await attestors()
  return client.open(
    TriMinter.createFromConfig(
      {
        attestors: keys.map(k => k.publicKey),
        threshold: THRESHOLD,
        epoch: 1,
        content: offchainContent(process.env.CONTENT_URL ?? 'https://t27.ai/tri/jetton.json'),
        walletCode: await compileWallet(),
      },
      await compileMinter(),
    ),
  )
}

async function balance(a: Address) {
  return rpc(() => client.getBalance(a))
}

/** Send from the deployer and wait until its seqno moves. */
async function sendAndWait(to: Address, value: bigint, opts: { body?: Cell; init?: { code: Cell; data: Cell } }) {
  const { key, wallet } = await deployer()
  const seqno = await rpc(() => wallet.getSeqno())
  await rpc(() =>
    wallet.sendTransfer({
      seqno,
      secretKey: key.secretKey,
      sendMode: SendMode.PAY_GAS_SEPARATELY | SendMode.IGNORE_ERRORS,
      messages: [internal({ to, value, bounce: false, body: opts.body, init: opts.init })],
    }),
  )
  for (let i = 0; i < 40; i++) {
    await sleep(3000)
    if ((await rpc(() => wallet.getSeqno())) > seqno) return
  }
  throw new Error('the deployer seqno did not move in 2 minutes')
}

const [cmd, ...args] = process.argv.slice(2)

if (cmd === 'wallet') {
  const { wallet } = await deployer()
  console.log(`deployer (testnet, v5r1): ${fmt(wallet.address)}`)
  console.log(`balance: ${fromNano(await balance(wallet.address))} TON`)
  console.log(`keys: ${join(HOME, 'deployer.json')} (0600)`)
} else if (cmd === 'attestors') {
  const keys = await attestors()
  keys.forEach((k, i) => console.log(`attestor ${i}: ${k.publicKey.toString('hex')}`))
  console.log(`quorum: ${THRESHOLD}-of-${keys.length}; keys: ${join(HOME, 'attestors.json')} (0600)`)
} else if (cmd === 'deploy') {
  const m = await minterContract()
  const state = await rpc(() => client.getContractState(m.address))
  if (state.state === 'active') {
    console.log(`already deployed: ${fmt(m.address)}`)
  } else {
    const { wallet } = await deployer()
    if ((await balance(wallet.address)) < toNano('0.6')) throw new Error('deployer needs >= 0.6 testnet TON')
    await sendAndWait(m.address, toNano('0.5'), { init: m.init })
    console.log(`deployed: ${fmt(m.address)}`)
  }
  writeFileSync(join(HOME, 'minter.json'), JSON.stringify({ network: 'testnet', minter: m.address.toRawString() }, null, 2) + '\n')
  console.log(`code hash: ${m.init!.code.hash().toString('hex')}`)
} else if (cmd === 'mint') {
  const owner = Address.parse(args[0] ?? '')
  if (owner.workChain !== 0) throw new Error('the minter pays workchain-0 addresses only')
  const amount = BigInt(args[1] ?? '0')
  const m = await minterContract()
  const keys = await attestors()
  const att: Attestation = {
    worker: owner.hash,
    workId: Buffer.from((args[2] ?? '').padStart(64, '0').slice(-64), 'hex'),
    chain: CHAIN_TON,
    amountMtri: amount,
    globalNonce: BigInt(args[3] ?? Date.now()),
    epoch: (await m.getTriState()).epoch,
  }
  const digest = attestationDigest(att)
  const sigs = new Map(keys.slice(0, THRESHOLD).map((k, i) => [i, sign(digest, k.secretKey)]))
  const body = mintBody({ att, sigs })
  await sendAndWait(m.address, toNano('0.1'), { body })
  await sleep(6000)
  console.log(`minted ${amount} mTRI (nonce ${att.globalNonce}) to ${fmt(owner)}`)
  console.log(`jetton wallet: ${fmt(await rpc(() => m.getWalletAddress(owner)))}`)
} else if (cmd === 'status') {
  const m = await minterContract()
  const j = await rpc(() => m.getJettonData())
  const s = await rpc(() => m.getTriState())
  console.log(`minter: ${fmt(m.address)}`)
  console.log(`supply: ${j.totalSupply} mTRI, minted_total: ${s.mintedTotal} / ${s.cap}, epoch ${s.epoch}, ${s.threshold}-of-${s.attestors}, admin: ${j.admin ?? 'none'}`)
} else {
  console.error('usage: testnet.ts wallet | attestors | deploy | mint <addr> <mTRI> [workIdHex] [nonce] | status')
  process.exit(2)
}
