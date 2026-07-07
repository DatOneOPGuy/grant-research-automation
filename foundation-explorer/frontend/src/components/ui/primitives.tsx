import type { ReactNode } from 'react'

export function Card({ children, className = '' }: {
  children: ReactNode; className?: string
}) {
  return (
    <div className={`bg-surface border border-line rounded-lg p-5 ${className}`}>
      {children}
    </div>
  )
}

export function CardTitle({ children }: { children: ReactNode }) {
  return (
    <h3 className="font-display text-lg font-medium text-primary mb-3">
      {children}
    </h3>
  )
}

export function Badge({ children, className = '' }: {
  children: ReactNode; className?: string
}) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>
      {children}
    </span>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded bg-line/60 ${className}`} />
  )
}

export function KPI({ label, value, sub }: {
  label: string; value: string; sub?: string
}) {
  return (
    <Card>
      <div className="font-display text-3xl font-semibold text-primary tabular">
        {value}
      </div>
      <div className="text-sm text-muted mt-1">{label}</div>
      {sub && <div className="text-xs text-scorelow mt-1">{sub}</div>}
    </Card>
  )
}

export function StatusPill({ status }: { status: string | null }) {
  if (status === 'Accepting Applications') {
    return <Badge className="bg-green-50 text-scorehigh">Accepting</Badge>
  }
  if (status === 'Contact First') {
    return <Badge className="bg-blue-50 text-blue-700">Contact first</Badge>
  }
  if (status === 'Invite Only') {
    return <Badge className="bg-amber-50 text-scoremid">Invite only</Badge>
  }
  return <Badge className="bg-gray-100 text-scorelow">Unknown</Badge>
}
