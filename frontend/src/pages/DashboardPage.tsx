import { useApi } from '../api/client';
import { Card, Kpi, Page, Status, ErrorBanner, Loading, Percent } from '../components/ui';

interface Summary {
  current_sprint?: string | null;
  sprint?: Record<string, unknown>;
  coverage?: { requirement?: number; story?: number; automation?: number; execution?: number };
  defects?: Record<string, number | null>;
  test_health?: { pass_rate?: number; total?: number; passed?: number; failed?: number };
  flaky?: number;
  regression?: { counts?: Record<string, number> };
  risks?: unknown[];
  ready_stories?: unknown[];
  recent_runs?: any[];
  velocity?: { sprint?: string; velocity?: number }[];
  defect_resolution?: {
    count?: number;
    distribution?: { label?: string; min_hours?: number; count?: number }[];
    stats?: { avg_hours?: number | null; p50_hours?: number | null; p95_hours?: number | null };
    over_7d_pct?: number;
    slowest?: any[];
  };
  open_defect_aging?: {
    open?: number;
    buckets?: { label?: string; count?: number }[];
    oldest?: { title?: string; days?: number };
    over_7d?: number;
    over_7d_pct?: number;
  };
  capacity?: { automated?: number; manual?: number; non_test?: number; total?: number; automated_pct?: number; manual_pct?: number; non_test_pct?: number };
  missing_ac_stories?: { count?: number; items?: any[] };
  pain_points?: { level?: string; title?: string; detail?: string }[];
  generated_at?: string;
}

export default function DashboardPage() {
  const { data, error, loading } = useApi<Summary>('/dashboard/summary');

  if (loading) return <Page title="Dashboard"><Loading /></Page>;
  if (error) return <Page title="Dashboard"><ErrorBanner message={error} /></Page>;
  if (!data) return <Page title="Dashboard"><Loading /></Page>;

  const cov = data.coverage || {};
  const def = data.defects || {};
  const health = data.test_health || {};
  const reg = data.regression?.counts || {};

  return (
    <Page title="Dashboard" subtitle={data.current_sprint ? `Active sprint: ${data.current_sprint}` : undefined}>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
        <Kpi label="Pass rate" value={`${health.pass_rate ?? 0}%`} tone="good" />
        <Kpi label="Tests" value={health.total ?? 0} sub={`${health.passed ?? 0} passed / ${health.failed ?? 0} failed`} />
        <Kpi label="Coverage" value={`${cov.requirement ?? 0}%`} tone="good" />
        <Kpi label="Open defects" value={def.open ?? 0} tone={Number(def.critical) > 0 ? 'bad' : undefined} sub={`${def.critical ?? 0} critical`} />
        <Kpi label="Time to resolve" value={fmtHours(data.defect_resolution?.stats?.avg_hours)} tone={resTone(data.defect_resolution?.stats?.avg_hours)} />
        <Kpi label="Manual effort" value={data.capacity ? `${data.capacity.manual_pct ?? 0}%` : '—'} tone="warn" sub={`${data.capacity?.manual ?? 0} of ${data.capacity?.total ?? 0} stories`} />
      </div>

      <PainPoints items={data.pain_points || []} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Time to resolve defects">
          <ResolutionChart data={data.defect_resolution} />
        </Card>
        <Card title="Capacity split: automation vs manual">
          <CapacityBar capacity={data.capacity} missingAc={data.missing_ac_stories?.count ?? 0} />
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Coverage by dimension">
          <div className="space-y-3">
            {([
              ['Requirements', cov.requirement],
              ['Stories', cov.story],
              ['Automation', cov.automation],
              ['Execution (30d)', cov.execution],
            ] as [string, number | undefined][]).map(([label, value]) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{label}</span>
                <Percent value={value ?? 0} />
              </div>
            ))}
          </div>
        </Card>

        <Card title="Age of open defects">
          <AgingBars data={data.open_defect_aging} />
        </Card>
      </div>

      <Card title="Recent test runs">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-600">
              <th className="px-2 py-2">Run</th>
              <th className="px-2 py-2">Framework</th>
              <th className="px-2 py-2">Env</th>
              <th className="px-2 py-2">Status</th>
              <th className="px-2 py-2">Passed</th>
              <th className="px-2 py-2">Failed</th>
            </tr>
          </thead>
          <tbody>
            {(data.recent_runs || []).map((r) => (
              <tr key={r.run_id} className="border-b border-gray-100">
                <td className="px-2 py-2 font-mono text-xs">{r.run_id}</td>
                <td className="px-2 py-2">{r.framework}</td>
                <td className="px-2 py-2">{r.environment}</td>
                <td className="px-2 py-2"><Status value={r.status} /></td>
                <td className="px-2 py-2">{r.passed}</td>
                <td className="px-2 py-2">{r.failed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </Page>
  );
}

/* ---- helpers ----------------------------------------------------------- */

function fmtHours(h: number | null | undefined): string {
  if (h == null) return '—';
  if (h >= 48) return `${Math.round((h / 24) * 10) / 10}d`;
  return `${Math.round(h)}h`;
}

function resTone(h: number | null | undefined): 'good' | 'bad' | 'warn' | undefined {
  if (h == null) return undefined;
  if (h <= 72) return 'good';
  if (h <= 168) return 'warn';
  return 'bad';
}

function bucketColor(label: string | undefined): string {
  if (label?.startsWith('<') || label?.startsWith('1 - 3')) return 'bg-green-500';
  if (label?.startsWith('3 - 7')) return 'bg-yellow-500';
  return 'bg-red-500';
}

/* ---- pain points -------------------------------------------------------- */
const LEVEL_STYLES: Record<string, { badge: string; border: string }> = {
  critical: { badge: 'bg-red-100 text-red-800', border: 'border-l-red-500' },
  warning: { badge: 'bg-yellow-100 text-yellow-800', border: 'border-l-yellow-500' },
  info: { badge: 'bg-blue-100 text-blue-800', border: 'border-l-accent' },
};

function PainPoints({ items }: { items: { level?: string; title?: string; detail?: string }[] }) {
  if (!items.length) return null;
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-3 font-display text-sm font-semibold text-brand">Executive focus</h3>
      <div className="space-y-3">
        {items.map((p, i) => {
          const style = LEVEL_STYLES[p.level || 'info'] || LEVEL_STYLES.info;
          return (
            <div key={i} className={`border-l-4 ${style.border} bg-mist/60 rounded-r-lg px-4 py-3`}>
              <div className="flex items-start gap-2">
                <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${style.badge}`}>
                  {p.level || 'info'}
                </span>
                <div>
                  <div className="text-sm font-semibold text-gray-800">{p.title}</div>
                  {p.detail && <div className="mt-0.5 text-xs text-slate">{p.detail}</div>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---- resolution chart --------------------------------------------------- */
function ResolutionChart({ data }: { data: Summary['defect_resolution'] }) {
  const dist = data?.distribution || [];
  const stats = data?.stats;
  const max = Math.max(1, ...dist.map((b) => b.count || 0));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4">
        <Stat label="Avg" value={fmtHours(stats?.avg_hours)} />
        <Stat label="Median" value={fmtHours(stats?.p50_hours)} />
        <Stat label="P95" value={fmtHours(stats?.p95_hours)} />
        <Stat label="> 7 days" value={data?.over_7d_pct != null ? `${data.over_7d_pct}%` : '—'} />
      </div>
      {dist.length ? (
        <div className="space-y-2">
          {dist.map((b) => (
            <div key={b.label} className="flex items-center gap-3">
              <span className="w-20 shrink-0 text-xs text-slate">{b.label}</span>
              <div className="h-4 flex-1 overflow-hidden rounded bg-gray-100">
                <div
                  className={`h-full rounded ${bucketColor(b.label)}`}
                  style={{ width: `${((b.count || 0) / max) * 100}%` }}
                />
              </div>
              <span className="w-8 text-right text-xs font-semibold text-gray-700">{b.count || 0}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="py-4 text-center text-sm text-slate">No resolved defects yet</p>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] font-medium uppercase tracking-wider text-slate">{label}</div>
      <div className="font-display text-lg font-semibold text-brand">{value}</div>
    </div>
  );
}

/* ---- capacity bar -------------------------------------------------------- */
function CapacityBar({ capacity, missingAc = 0 }: { capacity?: Summary['capacity']; missingAc?: number }) {
  if (!capacity || !capacity.total) {
    return <p className="py-4 text-center text-sm text-slate">No stories classified yet</p>;
  }
  const total = Math.max(capacity.total, 1);
  const a = (capacity.automated || 0) / total;
  const m = (capacity.manual || 0) / total;
  const n = (capacity.non_test || 0) / total;

  return (
    <div className="space-y-4">
      <div className="flex h-5 w-full overflow-hidden rounded-full bg-gray-100">
        <div className="bg-accent" style={{ width: `${a * 100}%` }} />
        <div className="bg-yellow-500" style={{ width: `${m * 100}%` }} />
        <div className="bg-gray-400" style={{ width: `${n * 100}%` }} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Legend color="bg-accent" label="Automated" count={capacity.automated || 0} pct={capacity.automated_pct || 0} />
        <Legend color="bg-yellow-500" label="Manual" count={capacity.manual || 0} pct={capacity.manual_pct || 0} />
        <Legend color="bg-gray-400" label="Non-test" count={capacity.non_test || 0} pct={capacity.non_test_pct || 0} />
      </div>
      {missingAc > 0 && (
        <p className="rounded-lg bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
          {missingAc} automated stor{missingAc === 1 ? 'y is' : 'ies are'} missing acceptance criteria.
        </p>
      )}
    </div>
  );
}

function Legend({ color, label, count, pct }: { color: string; label: string; count: number; pct: number }) {
  return (
    <div>
      <div className="flex items-center gap-1.5">
        <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
        <span className="text-xs text-slate">{label}</span>
      </div>
      <div className="mt-0.5 font-display text-lg font-semibold text-brand">
        {count} <span className="text-xs font-normal text-slate">({pct}%)</span>
      </div>
    </div>
  );
}

/* ---- open defect aging --------------------------------------------------- */
function AgingBars({ data }: { data?: Summary['open_defect_aging'] }) {
  const buckets = data?.buckets || [];
  const max = Math.max(1, ...buckets.map((b) => b.count || 0));
  if (!data?.open) return <p className="py-4 text-center text-sm text-slate">No open defects</p>;
  return (
    <div className="space-y-2">
      {buckets.map((b) => (
        <div key={b.label} className="flex items-center gap-3">
          <span className="w-20 shrink-0 text-xs text-slate">{b.label}</span>
          <div className="h-4 flex-1 overflow-hidden rounded bg-gray-100">
            <div className="h-full rounded bg-accent" style={{ width: `${((b.count || 0) / max) * 100}%` }} />
          </div>
          <span className="w-8 text-right text-xs font-semibold text-gray-700">{b.count || 0}</span>
        </div>
      ))}
      {data.oldest && (
        <p className="pt-1 text-xs text-slate">
          Oldest: <span className="font-semibold text-gray-700">{data.oldest.title}</span> ({data.oldest.days}d)
        </p>
      )}
    </div>
  );
}
