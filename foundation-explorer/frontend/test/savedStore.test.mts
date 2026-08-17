// Saved-folder store tests. No framework: Node 22 strips the types itself.
//   npm run test:saved
//
// Worth having because the migration path is destructive if it is wrong -- a
// user upgrading from the flat saved list would silently lose it, and nothing
// in the UI would report the loss.
let mem: Record<string,string> = {}
;(globalThis as any).localStorage = {
  getItem: (k: string) => (k in mem ? mem[k] : null),
  setItem: (k: string, v: string) => { mem[k] = String(v) },
}
;(globalThis as any).sessionStorage = (globalThis as any).localStorage

const SRC = process.argv[2] || new URL('../src/lib/savedStore.ts', import.meta.url).href
const load = async () => (await import(SRC + '?t=' + Math.random())).savedFoundationsStore
const ok = (l: string, c: boolean) => { console.log(`  ${c ? 'PASS' : 'FAIL'}  ${l}`); if (!c) process.exitCode = 1 }

console.log('1. migrates a legacy flat list into Favorites')
mem = { 'fe.saved.eins': JSON.stringify(['111','222','333']) }
let s = await load()
let folders = s.getFolders()
ok('one folder created', folders.length === 1)
ok('named Favorites', folders[0].name === 'Favorites')
ok('all three migrated', Object.keys(s.getMembership()).length === 3)
ok('each in Favorites', Object.values(s.getMembership()).every((v:any) => v[0] === folders[0].id))

console.log('\n2. fresh install seeds Favorites, empty')
mem = {}
s = await load()
ok('Favorites seeded', s.getFolders()[0]?.name === 'Favorites')
ok('nothing saved', Object.keys(s.getMembership()).length === 0)

console.log('\n3. multi-folder membership')
mem = {}; s = await load()
const fav = s.getFolders()[0]
const q1 = s.createFolder('Ask in Q1')
s.addTo('999', fav.id); s.addTo('999', q1.id)
ok('in two folders', s.getMembership()['999'].length === 2)
s.removeFrom('999', fav.id)
ok('still saved via the other', s.getMembership()['999'].length === 1)
s.removeFrom('999', q1.id)
ok('unsaved when last folder removed', !('999' in s.getMembership()))

console.log('\n4. Favorites is deletable, orphans dropped')
mem = {}; s = await load()
const f = s.getFolders()[0]
const other = s.createFolder('Other')
s.addTo('aaa', f.id)
s.addTo('bbb', f.id); s.addTo('bbb', other.id)
s.deleteFolder(f.id)
ok('Favorites gone', !s.getFolders().some((x:any) => x.id === f.id))
ok('orphan unsaved', !('aaa' in s.getMembership()))
ok('multi-folder survivor kept', s.getMembership()['bbb']?.length === 1)

console.log('\n5. every folder deletable, still usable after')
s.deleteFolder(other.id)
ok('no folders left', s.getFolders().length === 0)
ok('nothing saved', Object.keys(s.getMembership()).length === 0)
const fresh = s.createFolder('Rebuilt')
s.addTo('ccc', fresh.id)
ok('can save again from empty', s.getMembership()['ccc'].length === 1)

console.log('\n6. edge cases + persistence')
ok('duplicate name returns existing', s.createFolder('Rebuilt').id === fresh.id)
ok('blank name falls back', s.createFolder('   ').name === 'Untitled folder')
s.addTo('ccc', fresh.id)
ok('adding twice does not duplicate', s.getMembership()['ccc'].length === 1)
s.addTo('ddd', 'nonexistent-folder')
ok('cannot save into a missing folder', !('ddd' in s.getMembership()))
const before = JSON.stringify(s.getMembership())
const reloaded = await load()
ok('survives a reload', JSON.stringify(reloaded.getMembership()) === before)
