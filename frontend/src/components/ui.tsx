import React from 'react';
import { Link, NavLink } from 'react-router-dom';

/* ---- Status pill ------------------------------------------------------ */
const STATUS_COLORS: Record<string, string> = {
  PASSED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  ERROR: 'bg-red-100 text-red-800',
  SKIPPED: 'bg-gray-100 text-gray-600',
  COMPLETED: 'bg-green-100 text-green-800',
  RUNNING: 'bg-blue-100 text-blue-800',
  QUEUED: 'bg-yellow-100 text-yellow-800',
  SUCCEEDED: 'bg-green-100 text-green-800',
  COVERED: 'bg-green-100 text-green-800',
  PARTIALLY_COVERED: 'bg-yellow-100 text-yellow-800',
  NOT_COVERED: 'bg-red-100 text-red-800',
};

export function Status({ value }: { value?: string | null }) {
  const color = STATUS_COLORS[value || ''] || 'bg-gray-100 text-gray-600';
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>
      {value || '—'}
    </span>
  );
}

/* ---- Card ------------------------------------------------------------- */
export function Card({ title, children, action }: { title?: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between">
          {title && <h3 className="m-0 font-display text-sm font-semibold text-brand">{title}</h3>}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

/* ---- KPI -------------------------------------------------------------- */
export function Kpi({ label, value, sub, tone }: { label: string; value: React.ReactNode; sub?: string; tone?: 'good' | 'bad' | 'warn' }) {
  const toneCls = tone === 'good' ? 'text-green-700' : tone === 'bad' ? 'text-red-700' : tone === 'warn' ? 'text-yellow-700' : 'text-brand';
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wider text-slate">{label}</div>
      <div className={`mt-2 font-display text-3xl font-semibold tracking-tight ${toneCls}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate">{sub}</div>}
    </div>
  );
}

/* ---- Table ------------------------------------------------------------ */
export function Table({ headers, rows, empty }: { headers: string[]; rows: React.ReactNode[][]; empty?: string }) {
  if (!rows.length) {
    return <p className="py-6 text-center text-sm text-slate">{empty || 'No data'}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left">
            {headers.map((h) => (
              <th key={h} className="px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-gray-100 transition-colors hover:bg-mist">
              {r.map((c, j) => (
                <td key={j} className="px-3 py-2.5 text-gray-700">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---- Page shell ------------------------------------------------------- */
export function Page({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div>
      <header className="mb-5">
        <h1 className="m-0 font-display text-2xl font-semibold tracking-tight text-brand">{title}</h1>
        {subtitle && <p className="m-0 mt-1 text-sm text-slate">{subtitle}</p>}
        <div className="mt-3 h-1 w-12 rounded-full bg-accent" />
      </header>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

/* ---- State / error banner -------------------------------------------- */
export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      API error: {message}
    </div>
  );
}

export function Loading() {
  return <p className="py-8 text-center text-sm text-slate">Loading…</p>;
}

export function JsonLink({ to, children }: { to: string; children?: React.ReactNode }) {
  return (
    <Link to={to} className="text-accent underline-offset-2 hover:text-accent-dark hover:underline">
      {children}
    </Link>
  );
}

/* ---- Percent bar ------------------------------------------------------ */
export function Percent({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  const color = v >= 75 ? 'bg-green-500' : v >= 40 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-200">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${v}%` }} />
      </div>
      <span className="text-xs font-semibold text-slate">{value}%</span>
    </div>
  );
}

/* ---- Nav -------------------------------------------------------------- */
export const NAV_ITEMS: { to: string; label: string }[] = [
  { to: '/', label: 'Dashboard' },
  { to: '/coverage', label: 'Coverage' },
  { to: '/test-matrix', label: 'Test Matrix' },
  { to: '/test-cases', label: 'Test Cases' },
  { to: '/defects', label: 'Defects' },
  { to: '/flaky', label: 'Flaky Tests' },
  { to: '/risks', label: 'Risks' },
  { to: '/sprints', label: 'Sprints' },
  { to: '/velocity', label: 'Velocity' },
  { to: '/regression', label: 'Regression' },
  { to: '/test-runs', label: 'Test Runs' },
  { to: '/agents', label: 'Agents' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/reports', label: 'Reports' },
];

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full">
      <aside className="flex w-56 shrink-0 flex-col bg-brand">
        <div className="border-b border-white/10 px-5 py-5">
          <img src="/brand/logo.png" alt="CyberPro Consulting" className="h-10 w-auto" />
          <div className="mt-3 text-xs font-medium tracking-wide text-white/60">UAT Test Intelligence</div>
        </div>
        <nav className="flex-1 overflow-y-auto p-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `mb-0.5 block rounded-lg px-3 py-2 font-display text-sm ${
                  isActive ? 'bg-white/10 font-medium text-white' : 'text-white/70 transition-colors hover:bg-white/5 hover:text-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-white/10 px-5 py-4">
          <div className="text-xs text-white/40">CyberPro Consulting (Pty) Ltd</div>
        </div>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
