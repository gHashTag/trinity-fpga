import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { compileMinter, compileWallet, TON_DIR } from '../wrappers/TriMinter'

/**
 * Compile the minter and the reference wallet to build/*.boc and print their
 * code hashes. A deployed minter is checked against these hashes: same source,
 * same compiler (func-js pinned in package-lock.json), same hash.
 */

const out = join(TON_DIR, 'build')
mkdirSync(out, { recursive: true })

for (const [name, compile] of [
  ['tri_minter', compileMinter],
  ['jetton_wallet', compileWallet],
] as const) {
  const code = await compile()
  writeFileSync(join(out, `${name}.boc`), code.toBoc())
  console.log(`${name}.boc  code hash ${code.hash().toString('hex')}`)
}
