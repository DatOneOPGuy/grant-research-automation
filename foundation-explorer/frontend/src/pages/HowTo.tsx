// What every filter on the Foundations page actually means.
//
// Most of these are self-explanatory. The ones that are not are the ones that
// matter most -- coverage, evidence tier, the difference between percentage
// and dollars -- and getting them wrong produces a confident, wrong shortlist.
// So this page leads with the traps rather than reciting the controls in
// screen order.
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight } from 'lucide-react'

export default function HowTo() {
  return (
    <div className="max-w-3xl">
      <h1 className="font-display text-3xl font-semibold text-primary">
        How the filters work
      </h1>
      <p className="text-sm text-muted mt-1">
        Every control on the{' '}
        <Link to="/foundations" className="text-primary hover:underline">
          Foundations
        </Link>{' '}
        page, what it filters on, and where it will mislead you if you read it
        too quickly.
      </p>

      <Callout>
        <strong>The one thing worth knowing first.</strong> A percentage and a
        dollar amount answer different questions. A foundation can be{' '}
        <em>100% Christian</em> because it made one $5,000 grant to a church,
        while Lilly Endowment sits at 29% and gave $834 million. If you are
        looking for money, sort by <strong>Christian $</strong>. If you are
        looking for a funder whose whole identity is faith-based, sort by{' '}
        <strong>% Christian</strong> — and check the coverage figure underneath
        it before you trust it.
      </Callout>

      <Group title="Presets">
        <P>
          Five saved filter combinations, as starting points rather than
          answers. Each one just sets several filters at once — open the rail
          afterwards and you can see exactly what it did and adjust it.
        </P>
        <Defs items={[
          ['Reachable Christian funders',
            'Gives to Christian organisations and accepts applications. The '
            + 'shortest path to a list you can actually approach.'],
          ['High-confidence Christian',
            'Restricts to the authoritative evidence tier, so every classified '
            + 'dollar rests on an IRS code or a human review rather than an '
            + 'inference.'],
          ['Accepting applications',
            'Drops invite-only and contact-first funders.'],
          ['Catholic funders', 'Catholic recipients specifically.'],
          ['Evangelical funders', 'Evangelical and Protestant recipients.'],
          ['Major funders ($1M+)',
            'At least $1M paid, excluding testamentary trusts and DAF '
            + 'pass-throughs.'],
        ]} />
      </Group>

      <Group title="Recipient Faith">
        <P>
          This filters on <strong>who the foundation gave money to</strong>,
          not on what the foundation calls itself. A foundation with no
          religious language anywhere in its name can still be the largest
          Christian funder in your state, and this is the filter that finds it.
        </P>
        <Defs items={[
          ['Any Christian',
            'Evangelical/Protestant, Catholic, Orthodox and Christian '
            + '(unspecified) together. Tick the children instead if you need '
            + 'one tradition.'],
          ['Jewish · Muslim · Mormon/LDS · Christian Science · Other religion',
            'Other faith traditions, classified the same way.'],
          ['Secular',
            'Recipients we positively determined are not religious — not the '
            + 'same as unclassified.'],
          ['Unclassified',
            'Recipients we could not classify at all. Shown because hiding '
            + 'them would overstate everything else.'],
        ]} />

        <Sub>Evidence tier</Sub>
        <P>
          How strong the classification has to be before a dollar counts. This
          is the rigour dial, and it only ever moves numbers down.
        </P>
        <Defs items={[
          ['All evidence',
            'Everything, including recipients classified from their name or a '
            + 'funder’s stated purpose.'],
          ['High-confidence only',
            'IRS activity codes, IRS church coding, denominational group '
            + 'rulings and human review. Nothing inferred.'],
          ['Mission-text classified',
            'Only recipients classified from the wording of their own Form '
            + '990 — the organisation describing itself.'],
        ]} />
        <P>
          Switching to high-confidence tightens the numerator while leaving the
          denominator alone, so a foundation’s percentage can only fall.
          A figure that barely moves is a figure you can lean on.
        </P>

        <Sub>Minimum thresholds</Sub>
        <Defs items={[
          ['Min $ to selected tradition',
            'Filters out token giving. A funder that gave $500 to one church '
            + 'is technically a Christian funder and practically is not.'],
          ['Min # recipients of tradition',
            'Filters out one-offs. Three or more recipients suggests a '
            + 'pattern rather than a favour.'],
        ]} />
      </Group>

      <Group title="Giving">
        <Defs items={[
          ['Total paid (2023–24)',
            'Everything the foundation actually paid out across both tax '
            + 'years. Paid, not pledged.'],
          ['Median grant',
            'The single most useful number for sizing an ask. Half their '
            + 'grants were larger than this. A funder with a $2,000 median is '
            + 'not going to write you $250,000, whatever their total says.'],
          ['Min grants',
            'How many grants they made. A large total spread over four grants '
            + 'is a different funder from one spread over four hundred.'],
          ['Active year',
            'Gave in 2023, in 2024, or in either. Useful for spotting funders '
            + 'who have gone quiet.'],
        ]} />
      </Group>

      <Group title="Geography">
        <Defs items={[
          ['Foundation located in',
            'Where the foundation itself is. Region chips — Northeast, '
            + 'Bible Belt and so on — select whole state sets at once.'],
          ['Gives to state',
            'Where the money lands, which is often not where the foundation '
            + 'sits. This is usually the one you want.'],
          ['Gives internationally',
            'Sent money outside the US in the window.'],
          ['Mission region',
            'Groups the filing’s country codes into regions — Sub-Saharan '
            + 'Africa, Latin America, and so on — so you can filter by mission '
            + 'field rather than by country.'],
        ]} />
        <Note>
          Destinations come from the country code on the filing, which uses
          IRS/FIPS codes rather than ISO. Where a code could not be verified
          the money still counts as international but is left unplaced rather
          than assigned to a guessed country.
        </Note>
      </Group>

      <Group title="Reachability">
        <P>
          Whether you can approach them at all. Worth applying early: a perfect
          match that only funds by invitation is not a prospect.
        </P>
        <Defs items={[
          ['Application status',
            'Accepting applications, contact first, invite only, or unknown, '
            + 'as stated in the filing.'],
          ['Has website · Has email · Has contact person',
            'Contact details present in the filing. These cut hard — most '
            + 'foundations list none of them.'],
        ]} />
      </Group>

      <Group title="Foundation">
        <Defs items={[
          ['Total assets', 'The corpus. Indicates future capacity.'],
          ['Min revenue', 'Money coming in during the window.'],
          ['Application deadlines',
            'By season, specific months, or a month range that can wrap across '
            + 'the year end. There is a catch worth understanding — see below.'],
          ['Deadline kind',
            'Dated deadlines, rolling year-round applications, or none stated.'],
          ['Exclude testamentary trusts',
            'Bank-administered trusts distributing under a will. They rarely '
            + 'respond to outreach.'],
          ['Exclude micro-funds', 'Very small funders, to cut noise.'],
          ['Include zero-giving foundations',
            'Off by default. 28,129 foundations paid nothing in the window; '
            + 'they have no grants, no faith mix and no coverage, so they are '
            + 'hidden unless you ask.'],
          ['DAF pass-through',
            'Include, exclude, or show only donor-advised fund transfers. A '
            + 'DAF grant tells you a donor moved money, not where it ended up.'],
        ]} />
        <Note>
          A 990-PF carries no date on an individual grant, so a deadline filter
          describes <em>when a foundation asks to be approached</em> — the
          thing you schedule around — not when it wrote cheques.
        </Note>
      </Group>

      <Group title="Data Quality">
        <P>
          <strong>Coverage</strong> is the share of a foundation’s paid
          dollars we could attribute to an identifiable organisation and
          classify. It is the denominator behind every percentage on the page,
          and the reason two identical-looking funders can deserve very
          different levels of trust.
        </P>
        <Defs items={[
          ['Coverage band',
            'High, Moderate, Low, or Not Classifiable.'],
          ['Min coverage',
            'A floor, as a percentage. Setting this to 50% or more is the '
            + 'single best way to stop thin claims reaching your shortlist.'],
        ]} />
        <Callout tone="plain">
          <strong>100% Christian at 20% coverage</strong> means we classified a
          fifth of their giving and all of that fifth went to Christian
          organisations. The other four fifths could be anything.{' '}
          <strong>100% at 95% coverage</strong> is a genuinely different claim.
          The page never shows a percentage without its coverage figure
          underneath for exactly this reason.
        </Callout>
        <P>
          Where nothing at all could be classified you will see an em dash and{' '}
          <em>none classifiable</em> rather than 0%. Zero would assert the
          giving is non-Christian, which is a claim about the money; we know
          nothing about it either way.
        </P>
      </Group>

      <Group title="Reading a row">
        <Defs items={[
          ['The stacked bar',
            'Christian, non-Christian, unclassified, DAF pass-through, and '
            + 'not-attributable, drawn to scale of everything paid. The hatched '
            + 'segment is money the filing never tied to a named recipient — '
            + 'patient-assistance programs protected by HIPAA, recipient lists '
            + 'filed as PDF attachments — so there is nothing to classify.'],
          ['Christian $ / of $X',
            'Christian dollars over total paid, so the ratio is visible '
            + 'without arithmetic.'],
        ]} />
      </Group>

      <div className="mt-8 pt-5 border-t border-line flex flex-wrap gap-4
        text-sm">
        <Link to="/foundations"
          className="inline-flex items-center gap-1 text-primary
            hover:underline">
          Go to Foundations <ArrowRight size={14} />
        </Link>
        <Link to="/trust"
          className="inline-flex items-center gap-1 text-muted
            hover:text-primary">
          How the data is built and verified <ArrowRight size={14} />
        </Link>
      </div>
    </div>
  )
}

function Group({ title, children }: {
  title: string; children: React.ReactNode
}) {
  return (
    <section className="mt-7">
      <h2 className="font-display text-xl font-semibold text-primary mb-2">
        {title}
      </h2>
      <div className="space-y-3">{children}</div>
    </section>
  )
}

function Sub({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-sm font-semibold text-ink mt-4">{children}</h3>
  )
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted leading-relaxed">{children}</p>
}

function Defs({ items }: { items: [string, string][] }) {
  return (
    <dl className="space-y-2">
      {items.map(([term, description]) => (
        <div key={term} className="grid grid-cols-1 sm:grid-cols-[13rem_1fr]
          gap-x-4 gap-y-0.5">
          <dt className="text-sm font-medium text-ink">{term}</dt>
          <dd className="text-sm text-muted leading-relaxed">{description}</dd>
        </div>
      ))}
    </dl>
  )
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs text-muted border-l-2 border-line pl-3
      leading-relaxed">
      {children}
    </p>
  )
}

function Callout({ children, tone = 'warn' }: {
  children: React.ReactNode
  tone?: 'warn' | 'plain'
}) {
  const warn = tone === 'warn'
  return (
    <div className={`mt-5 rounded-lg border px-4 py-3 text-sm leading-relaxed
      ${warn
        ? 'border-accent/40 bg-accent/5 text-ink'
        : 'border-line bg-canvas text-muted'}`}>
      {warn && (
        <AlertTriangle size={14}
          className="inline-block mr-1.5 -mt-0.5 text-scoremid" />
      )}
      {children}
    </div>
  )
}
