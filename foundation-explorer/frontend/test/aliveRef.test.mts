// Guards the mount/unmount lifecycle of SavedProvider's `alive` ref.
//
// React StrictMode runs effects setup -> cleanup -> setup on mount in
// development. An effect written as
//
//     useEffect(() => () => { alive.current = false }, [])
//
// therefore leaves the ref false for the life of the app: it is only ever
// assigned in the cleanup. Every guarded state update then silently stops --
// reload() returns before its setState so the list never refreshes, and
// mutate()'s finally skips setBusy(false) so every control stays disabled
// after the first action. Folder creation reached the server and vanished.
//
// Nothing else catches this. It typechecks, it lints, and it only manifests
// under StrictMode, which is development-only -- so production was fine while
// local was completely broken.
import { readFileSync } from 'node:fs'

const SRC = new URL('../src/lib/SavedProvider.tsx', import.meta.url)
const src = readFileSync(SRC, 'utf8')
const ok = (l: string, c: boolean) => {
  console.log(`  ${c ? 'PASS' : 'FAIL'}  ${l}`)
  if (!c) process.exitCode = 1
}

console.log('SavedProvider alive-ref lifecycle')

// The effect must assign true on setup, not only false on cleanup.
const effect = src.match(/useEffect\(\(\) => \{[\s\S]*?alive\.current = true[\s\S]*?\}, \[\]\)/)
ok('sets alive.current = true on setup', effect !== null)
ok('still clears it on cleanup',
   /return \(\) => \{ alive\.current = false \}/.test(src))

// The shorthand that caused the bug must not come back.
ok('does not use the cleanup-only shorthand',
   !/useEffect\(\(\) => \(\) => \{ alive\.current = false \}, \[\]\)/.test(src))

// The guards it protects should still be there -- if they were removed the
// test above would pass while the reason for it had gone.
ok('reload still guards its state updates', src.includes('if (!alive.current) return'))
ok('mutate still guards setBusy', src.includes('if (alive.current) setBusy(false)'))
