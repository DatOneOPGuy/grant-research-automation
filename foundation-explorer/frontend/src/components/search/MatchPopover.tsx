// "Why is this here?" -- the evidence panel beside a search result.
//
// A ranked list whose ordering the user cannot account for is a list they have
// to take on faith. This shows the matched text from each index that
// contributed, with the hit terms highlighted, so a result reached through a
// grantee's mission statement is visibly that rather than mysterious.
import { createPortal } from 'react-dom'
import { MATCH_STYLE, type SearchMatch } from '../../lib/apiSearch'

/** Snippets are HTML-escaped server-side and then given <b> tags, so <b> is
 *  the only markup that can reach here.
 *
 *  This is load-bearing, not incidental. SQLite's snippet() does no escaping
 *  of its own, and the indexed text is 990-PF filing data we do not control --
 *  48,000+ rows already contain "<" or "&". search.py marks hits with control
 *  characters, escapes, then substitutes tags, precisely so that this render
 *  is safe. Do not change one side without the other. */
function Highlighted({ html }: { html: string }) {
  return <span dangerouslySetInnerHTML={{ __html: html }} />
}

export function MatchBadges({ matches }: { matches: SearchMatch[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {matches.map((m) => (
        <span key={m.field}
          className={`px-1.5 py-0.5 rounded border text-[10px] font-medium
            uppercase tracking-wide ${MATCH_STYLE[m.field].cls}`}>
          {MATCH_STYLE[m.field].short}
        </span>
      ))}
    </div>
  )
}

export default function MatchPopover({ matches, anchor, onClose }: {
  matches: SearchMatch[]
  anchor: { top: number; left: number }
  onClose: () => void
}) {
  // Portalled and fixed-positioned: the trigger lives inside a scrolling
  // results list, where the popover would otherwise be clipped.
  return createPortal(
    <div
      onMouseLeave={onClose}
      style={{ top: anchor.top, left: anchor.left }}
      className="fixed z-[70] w-80 rounded-lg border border-line bg-surface
        shadow-xl p-3 text-xs">
      <div className="text-[10px] uppercase tracking-wide text-muted mb-2">
        Why this matched
      </div>
      <div className="space-y-2.5">
        {matches.map((m) => (
          <div key={m.field}>
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className={`px-1.5 py-0.5 rounded border text-[10px]
                font-medium uppercase tracking-wide
                ${MATCH_STYLE[m.field].cls}`}>
                {MATCH_STYLE[m.field].short}
              </span>
              <span className="text-muted">{m.label}</span>
            </div>
            <div className="text-ink leading-snug [&_b]:bg-accent/30
              [&_b]:text-ink [&_b]:rounded-sm [&_b]:px-0.5">
              <Highlighted html={m.snippet} />
            </div>
            {m.detail && (
              <div className="text-muted mt-0.5 italic">{m.detail}</div>
            )}
          </div>
        ))}
      </div>
    </div>,
    document.body,
  )
}

export { Highlighted }
