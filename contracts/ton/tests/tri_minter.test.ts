import { beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { Blockchain, internal, type SandboxContract, type TreasuryContract } from '@ton/sandbox'
import { Address, beginCell, Cell, toNano, type Transaction } from '@ton/core'
import { keyPairFromSeed, sign, type KeyPair } from '@ton/crypto'
import {
  attestationDigest,
  CAP_MTRI,
  CHAIN_SOLANA,
  CHAIN_TON,
  compileMinter,
  compileWallet,
  Err,
  offchainContent,
  rotationDigest,
  TriMinter,
  workerAddress,
  type Attestation,
  type TriMinterConfig,
} from '../wrappers/TriMinter'

/**
 * The minter executed in a TON VM against the Zig oracle
 * (src/trinet/mint_authority.zig). Keys, digests and signatures are the
 * oracle's: same seeds (i+1, 0, ..., 0), same layout, RFC 8032 ed25519 on both
 * sides, so the bytes below are copied from the oracle's golden tests, not
 * recomputed here.
 */

const ORACLE_DIGEST = '9ce2cee577fd87a72b837d56c728b70a580e366f4a5b7339dba8146439c1dde7'
const ORACLE_ROTATION = '49f46c26595ebc0c2ead0e8fb4f9eaa38696db77077f5f3cf1e1b59c85afca77'
const ORACLE_PK0 = 'cecc1507dc1ddd7295951c290888f095adb9044d1b73d696e6df065d683bd4fc'
const ORACLE_SIG0 =
  '670a391db25b567d13262d640c396b9e1847879b9d63f212bb2e4cfea74bcce64170fa67c516c7ce707da7750e1795a0556554e32d9495b3c27de82df74b8203'
const ORACLE_SIG1 =
  'f1e57f4fe075f474cb8721821a3d77553b93de135fd646ef8ea2009231e1f38b4a133aa81bedf759bd565b32c6fdbc444103dff4a08fde26ef7da88dd3d3fc0c'

/** mint_authority.zig genKeys: seed[0] = i + 1, the rest zero. */
const key = (i: number): KeyPair => {
  const seed = Buffer.alloc(32)
  seed[0] = i + 1
  return keyPairFromSeed(seed)
}
const KEYS = [0, 1, 2, 3, 4, 5, 6].map(key)
const pub = (ks: KeyPair[]) => ks.map(k => k.publicKey)

/** mint_authority.zig sampleAtt. */
const sampleAtt = (nonce: bigint, amount: bigint, chain = CHAIN_TON, epoch = 1): Attestation => ({
  worker: Buffer.alloc(32, 7),
  workId: Buffer.alloc(32, 9),
  chain,
  amountMtri: amount,
  globalNonce: nonce,
  epoch,
})

/** Signatures by attestor index: `signers` maps index -> key that signs there. */
const signAt = (digest: Buffer, signers: Array<[number, KeyPair]>) =>
  new Map(signers.map(([i, k]) => [i, sign(digest, k.secretKey)]))

/** The exit code of the minter's own transaction for the last message sent. */
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

let minterCode: Cell
let walletCode: Cell
beforeAll(async () => {
  minterCode = await compileMinter()
  walletCode = await compileWallet()
})

describe('the oracle vectors, outside any chain', () => {
  it('the attestation digest is the oracle golden vector', () => {
    expect(attestationDigest(sampleAtt(1n, 5n)).toString('hex')).toBe(ORACLE_DIGEST)
  })

  it('keys and signatures are byte-identical to the oracle (RFC 8032)', () => {
    const d = attestationDigest(sampleAtt(1n, 5n))
    expect(KEYS[0].publicKey.toString('hex')).toBe(ORACLE_PK0)
    expect(sign(d, KEYS[0].secretKey).toString('hex')).toBe(ORACLE_SIG0)
    expect(sign(d, KEYS[1].secretKey).toString('hex')).toBe(ORACLE_SIG1)
  })

  it('the rotation digest is the oracle golden vector', () => {
    expect(rotationDigest(Buffer.alloc(32, 0x5a), 2, 2, pub(KEYS.slice(0, 3))).toString('hex')).toBe(
      ORACLE_ROTATION,
    )
  })
})

describe('tri_minter in the TON VM', () => {
  let chain: Blockchain
  let payer: SandboxContract<TreasuryContract>
  let minter: SandboxContract<TriMinter>

  const deploy = async (over: Partial<TriMinterConfig> = {}) => {
    const m = chain.openContract(
      TriMinter.createFromConfig(
        {
          attestors: pub(KEYS.slice(0, 3)),
          threshold: 2,
          epoch: 1,
          content: offchainContent('https://t27.ai/tri/jetton.json'),
          walletCode,
          ...over,
        },
        minterCode,
      ),
    )
    await m.sendDeploy(payer.getSender(), toNano('1'))
    return m
  }

  /** The jetton balance of `owner`, or 0 if its wallet does not exist. */
  const balanceOf = async (owner: Address, m = minter) => {
    const w = await m.getWalletAddress(owner)
    const acc = await chain.getContract(w)
    if (acc.accountState?.type !== 'active') return 0n
    return (await acc.get('get_wallet_data')).stackReader.readBigNumber()
  }

  /** Mint `att` signed at the oracle's indices 0 and 1. */
  const mint = (att: Attestation, signers: Array<[number, KeyPair]> = [[0, KEYS[0]], [1, KEYS[1]]], value?: bigint) =>
    minter.sendMintOnAtt(payer.getSender(), { att, sigs: signAt(attestationDigest(att), signers), value })

  beforeEach(async () => {
    chain = await Blockchain.create()
    payer = await chain.treasury('payer')
    minter = await deploy()
  })

  it('genesis: zero supply, no admin, the cap is 3^21 TRI in mTRI', async () => {
    const j = await minter.getJettonData()
    expect(j.totalSupply).toBe(0n)
    expect(j.mintable).toBe(true)
    expect(j.admin).toBeNull()
    expect(j.walletCode.hash().equals(walletCode.hash())).toBe(true)
    const s = await minter.getTriState()
    expect(s).toEqual({ mintedTotal: 0n, cap: CAP_MTRI, epoch: 1, threshold: 2, attestors: 3 })
    expect(CAP_MTRI).toBe(3n ** 21n * 1000n)
  })

  it("a valid 2-of-3 quorum -- the oracle's own signature bytes -- mints exactly the amount to the worker", async () => {
    const att = sampleAtt(1n, 5n)
    const sigs = new Map([
      [0, Buffer.from(ORACLE_SIG0, 'hex')],
      [1, Buffer.from(ORACLE_SIG1, 'hex')],
    ])
    const r = await minter.sendMintOnAtt(payer.getSender(), { att, sigs })
    expect(exitOn(r.transactions, minter.address)).toBe(0)
    expect(await balanceOf(workerAddress(att.worker))).toBe(5n)
    expect((await minter.getJettonData()).totalSupply).toBe(5n)
    expect((await minter.getTriState()).mintedTotal).toBe(5n)
    expect(await minter.getIsSpent(1n)).toBe(true)
  })

  it('a sub-quorum mints nothing', async () => {
    const r = await mint(sampleAtt(1n, 5n), [[0, KEYS[0]]])
    expect(exitOn(r.transactions, minter.address)).toBe(Err.subQuorum)
    expect((await minter.getJettonData()).totalSupply).toBe(0n)
    expect(await minter.getIsSpent(1n)).toBe(false)
  })

  it('a repeated signature from one attestor cannot stuff the quorum', async () => {
    // Attestor 0's signature placed again under index 1: index 1 holds key 1,
    // so it does not verify there.
    const r = await mint(sampleAtt(1n, 5n), [[0, KEYS[0]], [1, KEYS[0]]])
    expect(exitOn(r.transactions, minter.address)).toBe(Err.subQuorum)
  })

  it('a non-attestor signature counts for nothing, at any index', async () => {
    const outsider = KEYS[3]
    let r = await mint(sampleAtt(1n, 5n), [[0, KEYS[0]], [1, outsider]])
    expect(exitOn(r.transactions, minter.address)).toBe(Err.subQuorum)
    r = await mint(sampleAtt(1n, 5n), [[0, KEYS[0]], [3, outsider]]) // index past N
    expect(exitOn(r.transactions, minter.address)).toBe(Err.subQuorum)
  })

  it('a spent nonce is refused -- no double-mint', async () => {
    const att = sampleAtt(1n, 5n)
    await mint(att)
    const r = await mint(att)
    expect(exitOn(r.transactions, minter.address)).toBe(Err.replayed)
    expect((await minter.getJettonData()).totalSupply).toBe(5n) // still 5, not 10
  })

  it('a quorum for Solana does not mint on TON (the chain is signed)', async () => {
    const r = await mint(sampleAtt(1n, 5n, CHAIN_SOLANA))
    expect(exitOn(r.transactions, minter.address)).toBe(Err.wrongChain)
  })

  it("an attestation for another epoch is refused", async () => {
    const r = await mint(sampleAtt(1n, 5n, CHAIN_TON, 2))
    expect(exitOn(r.transactions, minter.address)).toBe(Err.wrongEpoch)
  })

  it('a mint over the cap is refused and consumes no nonce', async () => {
    minter = await deploy({ mintedTotal: CAP_MTRI - 3n, content: offchainContent('near-cap') })
    const r = await mint(sampleAtt(1n, 5n))
    expect(exitOn(r.transactions, minter.address)).toBe(Err.overCap)
    expect(await minter.getIsSpent(1n)).toBe(false)
    // ...and what fits under the cap still mints.
    const ok = await mint(sampleAtt(2n, 3n))
    expect(exitOn(ok.transactions, minter.address)).toBe(0)
    expect((await minter.getTriState()).mintedTotal).toBe(CAP_MTRI)
  })

  it('a zero-amount attestation is refused', async () => {
    const r = await mint(sampleAtt(1n, 0n))
    expect(exitOn(r.transactions, minter.address)).toBe(Err.zeroAmount)
  })

  it('a mint that cannot pay for the wallet is refused before anything is spent', async () => {
    const r = await mint(sampleAtt(1n, 5n), undefined, toNano('0.01'))
    expect(exitOn(r.transactions, minter.address)).toBe(Err.lowValue)
    expect(await minter.getIsSpent(1n)).toBe(false)
  })

  it('anyone may carry the attestation; the TRI still goes to the worker', async () => {
    const stranger = await chain.treasury('stranger')
    const att = sampleAtt(1n, 5n)
    await minter.sendMintOnAtt(stranger.getSender(), {
      att,
      sigs: signAt(attestationDigest(att), [[0, KEYS[0]], [1, KEYS[1]]]),
    })
    expect(await balanceOf(workerAddress(att.worker))).toBe(5n)
    expect(await balanceOf(stranger.address)).toBe(0n)
  })

  describe('a worker that is a real wallet', () => {
    let worker: SandboxContract<TreasuryContract>
    let att: Attestation

    beforeEach(async () => {
      worker = await chain.treasury('worker')
      att = { ...sampleAtt(1n, 5n), worker: worker.address.hash }
      await mint(att)
    })

    it('get_wallet_address names the wallet the mint deployed', async () => {
      expect(await balanceOf(worker.address)).toBe(5n)
    })

    it('the minted TRI moves like any jetton (reference wallet, TEP-74 transfer)', async () => {
      const friend = await chain.treasury('friend')
      const from = await minter.getWalletAddress(worker.address)
      await worker.send({
        to: from,
        value: toNano('0.1'),
        body: beginCell()
          .storeUint(0x0f8a7ea5, 32)
          .storeUint(0, 64)
          .storeCoins(2n)
          .storeAddress(friend.address)
          .storeAddress(worker.address)
          .storeMaybeRef(null)
          .storeCoins(0)
          .storeBit(false)
          .endCell(),
      })
      expect(await balanceOf(worker.address)).toBe(3n)
      expect(await balanceOf(friend.address)).toBe(2n)
      expect((await minter.getJettonData()).totalSupply).toBe(5n)
    })

    it('a burn lowers circulation; the cap counter does not reopen', async () => {
      const w = await minter.getWalletAddress(worker.address)
      await worker.send({
        to: w,
        value: toNano('0.1'),
        body: beginCell()
          .storeUint(0x595f07bc, 32)
          .storeUint(0, 64)
          .storeCoins(2n)
          .storeAddress(worker.address)
          .storeMaybeRef(null)
          .endCell(),
      })
      expect(await balanceOf(worker.address)).toBe(3n)
      expect((await minter.getJettonData()).totalSupply).toBe(3n)
      expect((await minter.getTriState()).mintedTotal).toBe(5n)
    })
  })

  it('a burn notification from anything but a TRI wallet is refused', async () => {
    const forger = await chain.treasury('forger')
    await mint(sampleAtt(1n, 5n))
    const r = await forger.send({
      to: minter.address,
      value: toNano('0.1'),
      body: beginCell()
        .storeUint(0x7bdd97de, 32)
        .storeUint(0, 64)
        .storeCoins(5n)
        .storeAddress(forger.address)
        .storeAddress(forger.address)
        .endCell(),
    })
    expect(exitOn(r.transactions, minter.address)).toBe(Err.notWallet)
    expect((await minter.getJettonData()).totalSupply).toBe(5n)
  })

  it('there is no admin op: anything else is refused', async () => {
    for (const op of [21 /* reference minter's mint */, 3 /* change_admin */, 4 /* change_content */]) {
      const r = await payer.send({
        to: minter.address,
        value: toNano('0.1'),
        body: beginCell().storeUint(op, 32).storeUint(0, 64).storeAddress(payer.address).endCell(),
      })
      expect(exitOn(r.transactions, minter.address)).toBe(Err.unknownOp)
    }
    expect((await minter.getJettonData()).totalSupply).toBe(0n)
  })

  it('an external message cannot reach it', async () => {
    await expect(
      chain.sendMessage({
        info: { type: 'external-in', dest: minter.address, importFee: 0n },
        body: beginCell().storeUint(0x54524931, 32).endCell(),
      }),
    ).rejects.toThrow()
  })

  it('a bounced mint drops circulation but keeps the nonce spent', async () => {
    // Simulate the worker wallet refusing internal_transfer: the network
    // returns 0xFFFFFFFF ++ the first bits of the body to the minter.
    await mint(sampleAtt(1n, 5n))
    const w = await minter.getWalletAddress(workerAddress(sampleAtt(1n, 5n).worker))
    await chain.sendMessage(
      internal({
        from: w,
        to: minter.address,
        value: toNano('0.01'),
        bounced: true,
        body: beginCell()
          .storeUint(0xffffffff, 32)
          .storeUint(0x178d4519, 32)
          .storeUint(0, 64)
          .storeCoins(5n)
          .endCell(),
      }),
    )
    expect((await minter.getJettonData()).totalSupply).toBe(0n)
    expect((await minter.getTriState()).mintedTotal).toBe(5n)
    expect(await minter.getIsSpent(1n)).toBe(true)
  })

  describe('rotation: the current quorum, and only it, hands over the mint', () => {
    const NEW = KEYS.slice(3, 6)
    const rotateSigs = (m: SandboxContract<TriMinter>, signers: Array<[number, KeyPair]>, epoch = 2) =>
      signAt(rotationDigest(m.address.hash, epoch, 2, pub(NEW)), signers)

    it('a 2-of-3 rotation moves the mint to the new set and the next epoch', async () => {
      const r = await minter.sendRotate(payer.getSender(), {
        newEpoch: 2,
        threshold: 2,
        keys: pub(NEW),
        sigs: rotateSigs(minter, [[0, KEYS[0]], [2, KEYS[2]]]),
      })
      expect(exitOn(r.transactions, minter.address)).toBe(0)
      expect(await minter.getTriState()).toMatchObject({ epoch: 2, threshold: 2, attestors: 3 })

      // The old set's attestation, even freshly signed for epoch 1, is dead.
      const old = await mint(sampleAtt(1n, 5n))
      expect(exitOn(old.transactions, minter.address)).toBe(Err.wrongEpoch)
      // The old set signing for epoch 2 is not a quorum of the new set.
      const sneaky = await mint(sampleAtt(1n, 5n, CHAIN_TON, 2))
      expect(exitOn(sneaky.transactions, minter.address)).toBe(Err.subQuorum)
      // The new set mints.
      const ok = await mint(sampleAtt(1n, 5n, CHAIN_TON, 2), [[0, NEW[0]], [1, NEW[1]]])
      expect(exitOn(ok.transactions, minter.address)).toBe(0)
    })

    it('a sub-quorum cannot rotate', async () => {
      const r = await minter.sendRotate(payer.getSender(), {
        newEpoch: 2,
        threshold: 2,
        keys: pub(NEW),
        sigs: rotateSigs(minter, [[0, KEYS[0]]]),
      })
      expect(exitOn(r.transactions, minter.address)).toBe(Err.subQuorum)
      expect((await minter.getTriState()).epoch).toBe(1)
    })

    it('a rotation must be exactly one epoch forward', async () => {
      const r = await minter.sendRotate(payer.getSender(), {
        newEpoch: 3,
        threshold: 2,
        keys: pub(NEW),
        sigs: rotateSigs(minter, [[0, KEYS[0]], [1, KEYS[1]]], 3),
      })
      expect(exitOn(r.transactions, minter.address)).toBe(Err.wrongEpoch)
    })

    it('a rotation signed for one minter cannot be replayed on another', async () => {
      const twin = await deploy({ content: offchainContent('twin') }) // same keys, other address
      expect(twin.address.equals(minter.address)).toBe(false)
      const r = await twin.sendRotate(payer.getSender(), {
        newEpoch: 2,
        threshold: 2,
        keys: pub(NEW),
        sigs: rotateSigs(minter, [[0, KEYS[0]], [1, KEYS[1]]]), // signed for `minter`
      })
      expect(exitOn(r.transactions, twin.address)).toBe(Err.subQuorum)
    })

    it('an impossible threshold is refused', async () => {
      for (const threshold of [0, 4]) {
        const r = await minter.sendRotate(payer.getSender(), {
          newEpoch: 2,
          threshold,
          keys: pub(NEW),
          sigs: new Map(),
        })
        expect(exitOn(r.transactions, minter.address)).toBe(Err.badAttestors)
      }
    })
  })
})
