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
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${color}`}>
      {value || '—'}
    </span>
  );
}

/* ---- Card ------------------------------------------------------------- */
export function Card({ title, children, action }: { title?: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between">
          {title && <h3 className="m-0 text-sm font-semibold text-gray-700">{title}</h3>}
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
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${toneCls}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-gray-500">{sub}</div>}
    </div>
  );
}

/* ---- Table ------------------------------------------------------------ */
export function Table({ headers, rows, empty }: { headers: string[]; rows: React.ReactNode[][]; empty?: string }) {
  if (!rows.length) {
    return <p className="py-6 text-center text-sm text-gray-400">{empty || 'No data'}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left">
            {headers.map((h) => (
              <th key={h} className="px-2 py-2 font-semibold text-gray-600">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
              {r.map((c, j) => (
                <td key={j} className="px-2 py-2 text-gray-700">
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
      <header className="mb-4">
        <h1 className="m-0 text-xl font-bold text-brand">{title}</h1>
        {subtitle && <p className="m-0 mt-1 text-sm text-gray-500">{subtitle}</p>}
      </header>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

/* ---- State / error banner -------------------------------------------- */
export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      API error: {message}
    </div>
  );
}

export function Loading() {
  return <p className="py-8 text-center text-sm text-gray-400">Loading…</p>;
}

export function JsonLink({ to, children }: { to: string; children?: React.ReactNode }) {
  return (
    <Link to={to} className="text-brand underline-offset-2 hover:underline">
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
        <div className={`h-full ${color}`} style={{ width: `${v}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-600">{value}%</span>
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
      <aside className="w-52 shrink-0 border-r border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-4 py-4">
          <div className="text-base font-bold text-brand">UAT Intelligence</div>
          <div className="text-xs text-gray-400">Test Management Platform</div>
        </div>
        <nav className="p-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `block rounded px-3 py-1.5 text-sm ${
                  isActive ? 'bg-brand text-white' : 'text-gray-700 hover:bg-gray-100'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
