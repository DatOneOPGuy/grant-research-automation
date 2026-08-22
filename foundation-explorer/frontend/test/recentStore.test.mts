// Recently-viewed store tests. No framework: Node strips the types itself.
//   npm run test:recent
//
// The snapshot-identity tests are the reason this file exists. getRecent is
// consumed by useSyncExternalStore, which compares snapshots by reference and
// re-reads after every render. An early version parsed localStorage afresh on
// each call, so every render produced a new array, React saw the store as
// perpetually changed, and the whole page died with "The result of
// getSnapshot should be cached to avoid an infinite loop". Nothing in the
// types or the linter catches that; only a test for reference equality does.
let mem: Record<string, string> = {}
;(globalThis as any).localStorage = {
  getItem: (k: string) => (k in mem ? mem[k] : null),
  setItem: (k: string, v: string) => { mem[k] = String(v) },
  removeItem: (k: string) => { delete mem[k] },
}
;(globalThis as any).window = { addEventListener() {}, removeEventListener() {} }

const SRC = process.argv[2]
  || new URL('../src/lib/recentStore.ts', import.meta.url).href
const load = async () => await import(SRC + '?t=' + Math.random())
const ok = (l: string, c: boolean) => {
  console.log(`  ${c ? 'PASS' : 'FAIL'}  ${l}`)
  if (!c) process.exitCode = 1
}

console.log('1. records views, most recent first')
mem = {}
let s = await load()
s.recordView({ ein: '111', name: 'Alpha', city: 'A', state: 'CA' })
s.recordView({ ein: '222', name: 'Beta', city: 'B', state: 'NY' })
ok('two entries', s.getRecent().length === 2)
ok('most recent first', s.getRecent()[0].ein === '222')
ok('carries the name', s.getRecent()[0].name === 'Beta')
ok('stamped with a time', typeof s.getRecent()[0].viewedAt === 'string')

console.log('\n2. re-viewing moves to front rather than duplicating')
s.recordView({ ein: '111', name: 'Alpha', city: 'A', state: 'CA' })
ok('still two entries', s.getRecent().length === 2)
ok('moved to front', s.getRecent()[0].ein === '111')

console.log('\n3. snapshot identity (the useSyncExternalStore contract)')
const a = s.getRecent()
const b = s.getRecent()
ok('same reference when unchanged', a === b)
s.recordView({ ein: '333', name: 'Gamma', city: null, state: null })
ok('new reference after a write', s.getRecent() !== a)
const c = s.getRecent()
ok('stable again after the write', s.getRecent() === c)
ok('server snapshot is stable', s.getRecentServerSnapshot() === s.getRecentServerSnapshot())

console.log('\n4. removal and clearing')
s.removeRecent('333')
ok('entry removed', !s.getRecent().some((e: any) => e.ein === '333'))
ok('reference changed after removal', s.getRecent() !== c)
s.clearRecent()
ok('cleared', s.getRecent().length === 0)

console.log('\n5. capped, newest kept')
mem = {}; s = await load()
for (let i = 0; i < 40; i++) {
  s.recordView({ ein: String(i).padStart(9, '0'), name: `F${i}`, city: null, state: null })
}
ok('capped at 25', s.getRecent().length === 25)
ok('kept the newest', s.getRecent()[0].name === 'F39')
ok('dropped the oldest', !s.getRecent().some((e: any) => e.name === 'F0'))

console.log('\n6. survives corrupt or foreign storage')
mem = { 'fe.recent.v1': 'not json at all' }
s = await load()
ok('corrupt value ignored', s.getRecent().length === 0)
mem = { 'fe.recent.v1': JSON.stringify([{ nope: true }, { ein: 'x', name: 'Ok' }]) }
s = await load()
ok('malformed entries filtered', s.getRecent().length === 1)
ok('good entry kept', s.getRecent()[0].name === 'Ok')

console.log('\n7. a write that throws must not break the caller')
mem = {}
s = await load()
;(globalThis as any).localStorage.setItem = () => { throw new Error('quota') }
let threw = false
try { s.recordView({ ein: '999', name: 'Quota', city: null, state: null }) }
catch { threw = true }
ok('recordView swallows storage failure', !threw)
