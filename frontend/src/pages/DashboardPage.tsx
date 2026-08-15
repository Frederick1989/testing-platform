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
  defect_trend?: { date?: string; opened?: number; closed?: number }[];
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
        <Kpi label="Flaky" value={data.flaky ?? 0} tone="warn" />
        <Kpi label="Regression" value={reg.new_failures ?? 0} tone={Number(reg.new_failures) > 0 ? 'bad' : 'good'} />
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

        <Card title="Defect trend (30d)">
          <DefectTrend data={data.defect_trend || []} />
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

function DefectTrend({ data }: { data: { date?: string; opened?: number; closed?: number }[] }) {
  if (!data.length) return <p className="py-4 text-center text-sm text-gray-400">No trend data</p>;
  return (
    <div className="flex h-40 items-end gap-1">
      {data.map((d) => (
        <div key={d.date} className="flex flex-1 flex-col items-center justify-end gap-1">
          <div className="flex gap-0.5 w-full justify-center">
            <div title={`opened ${d.opened ?? 0}`} className="w-3 rounded-t bg-brand" style={{ height: `${Math.min(100, (d.opened ?? 0) * 8)}px` }} />
            <div title={`closed ${d.closed ?? 0}`} className="w-3 rounded-t bg-green-500" style={{ height: `${Math.min(100, (d.closed ?? 0) * 8)}px` }} />
          </div>
          <span className="text-[10px] text-gray-400">{d.date?.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}
