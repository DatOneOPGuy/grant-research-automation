// The Advanced filter group must account for exactly what it hides.
//
// Filters inside "Advanced" are collapsed by default, so the count on its
// toggle is the only signal that something in there is narrowing the results.
// If a key is used inside the group but missing from ADVANCED_KEYS, a user can
// set it, collapse the group, and lose track of why their result set shrank --
// with the badge reading zero. If a key is counted but lives in one of the
// always-visible sections above, the badge inflates for something in plain
// sight. Both are silent; neither is caught by the typechecker.
import { readFileSync } from 'node:fs'

const dir = new URL('../src/', import.meta.url)
const panel = readFileSync(new URL('components/foundations/FilterPanel.tsx', dir), 'utf8')
const api = readFileSync(new URL('lib/apiV5.ts', dir), 'utf8')
const ok = (l: string, c: boolean) => {
  console.log(`  ${c ? 'PASS' : 'FAIL'}  ${l}`)
  if (!c) process.exitCode = 1
}

const declared = new Set(
  [...(panel.match(/ADVANCED_KEYS[^=]*=\s*\[([\s\S]*?)\]/)?.[1] ?? '')
    .matchAll(/'([a-z_]+)'/g)].map((m) => m[1]))

const block = panel.slice(panel.indexOf('<Advanced filters='),
                          panel.indexOf('</Advanced>'))
const used = new Set([...block.matchAll(/filters\.([a-z_]+)/g)].map((m) => m[1]))

const fields = new Set(
  [...(api.match(/export const defaultV5Filters[^{]*\{([\s\S]*?)\n\}/)?.[1] ?? '')
    .matchAll(/^\s*([a-z_]+):/gm)].map((m) => m[1]))

console.log('Advanced filter accounting')
ok('every declared key is a real filter field',
   [...declared].every((k) => fields.has(k)))
ok('every filter used inside Advanced is counted',
   [...used].every((k) => declared.has(k)))
ok('nothing counted that lives outside Advanced',
   [...declared].every((k) => used.has(k)))
ok('the group is not empty', declared.size > 0 && used.size > 0)

console.log('\nPrimary sections stay above the fold')
const order = [...panel.matchAll(/<Section title="([^"]+)"/g)].map((m) => m[1])
const advIdx = panel.indexOf('<Advanced filters=')
const primary = [...panel.matchAll(/<Section title="([^"]+)"/g)]
  .filter((m) => m.index! < advIdx).map((m) => m[1])
ok('Geography, Reachability and Recipient Faith come first',
   JSON.stringify(primary) === JSON.stringify(['Geography', 'Reachability', 'Recipient Faith']))
ok('Giving, Foundation and Data Quality are inside Advanced',
   ['Giving', 'Foundation', 'Data Quality'].every((t) => order.indexOf(t) >= 0
     && panel.indexOf(`<Section title="${t}"`) > advIdx))
