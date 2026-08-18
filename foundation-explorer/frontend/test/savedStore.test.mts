// LocalSavedStore tests. No framework: Node 22 strips the types itself.
//   npm run test:saved
//
// This store is now only used by the static demo build -- the live app keeps
// folders in Postgres, shared across the team. It is still worth testing
// because the demo is what reviewers see, and because it is the reference
// implementation of the SavedFoundationsStore contract: the two stores must
// agree on folder semantics or the demo would misrepresent the product.
let mem: Record<string,string> = {}
;(globalThis as any).localStorage = {
  getItem: (k: string) => (k in mem ? mem[k] : null),
  setItem: (k: string, v: string) => { mem[k] = String(v) },
}
;(globalThis as any).sessionStorage = (globalThis as any).localStorage

const SRC = process.argv[2] || new URL('../src/lib/savedStore.ts', import.meta.url).href
const load = async () => new (await import(SRC + '?t=' + Math.random())).LocalSavedStore()
const ok = (l: string, c: boolean) => { console.log(`  ${c ? 'PASS' : 'FAIL'}  ${l}`); if (!c) process.exitCode = 1 }

console.log('1. fresh install is empty')
mem = {}
let s = await load()
let state = await s.load()
ok('no folders', state.folders.length === 0)
ok('nothing saved', Object.keys(state.members).length === 0)

console.log('\n2. a pre-accounts saved list is ignored, not migrated')
// Folders are team state now. Silently promoting one browser's private list
// into a shared team folder would publish it to colleagues who never saw it.
mem = { 'fe.saved.eins': JSON.stringify(['111','222','333']) }
s = await load()
state = await s.load()
ok('legacy key not read', Object.keys(state.members).length === 0)

console.log('\n3. multi-folder membership')
mem = {}; s = await load()
const fav = await s.createFolder('Favorites')
const q1 = await s.createFolder('Ask in Q1')
await s.addTo('999', fav.id); await s.addTo('999', q1.id)
ok('in two folders', (await s.load()).members['999'].length === 2)
await s.removeFrom('999', fav.id)
ok('still saved via the other', (await s.load()).members['999'].length === 1)
await s.removeFrom('999', q1.id)
ok('unsaved when last folder removed', !('999' in (await s.load()).members))

console.log('\n4. deleting a folder drops its orphans')
mem = {}; s = await load()
const f = await s.createFolder('Favorites')
const other = await s.createFolder('Other')
await s.addTo('aaa', f.id)
await s.addTo('bbb', f.id); await s.addTo('bbb', other.id)
await s.deleteFolder(f.id)
state = await s.load()
ok('folder gone', !state.folders.some((x:any) => x.id === f.id))
ok('orphan unsaved', !('aaa' in state.members))
ok('multi-folder survivor kept', state.members['bbb']?.length === 1)

console.log('\n5. every folder deletable, still usable after')
await s.deleteFolder(other.id)
state = await s.load()
ok('no folders left', state.folders.length === 0)
ok('nothing saved', Object.keys(state.members).length === 0)
const fresh = await s.createFolder('Rebuilt')
await s.addTo('ccc', fresh.id)
ok('can save again from empty', (await s.load()).members['ccc'].length === 1)

console.log('\n6. edge cases + persistence')
ok('duplicate name returns existing', (await s.createFolder('Rebuilt')).id === fresh.id)
ok('case-insensitive duplicate too', (await s.createFolder('REBUILT')).id === fresh.id)
ok('blank name falls back', (await s.createFolder('   ')).name === 'Untitled folder')
await s.addTo('ccc', fresh.id)
ok('adding twice does not duplicate', (await s.load()).members['ccc'].length === 1)
await s.addTo('ddd', 'nonexistent-folder')
ok('cannot save into a missing folder', !('ddd' in (await s.load()).members))
await s.removeAll('ccc')
ok('removeAll unsaves everywhere', !('ccc' in (await s.load()).members))
const before = JSON.stringify((await s.load()).members)
const reloaded = await load()
ok('survives a reload', JSON.stringify((await reloaded.load()).members) === before)
