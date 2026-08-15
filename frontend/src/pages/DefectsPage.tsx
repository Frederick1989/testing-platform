import { useApi } from '../api/client';
import { Card, Kpi, Page, Status, ErrorBanner, Loading, Table } from '../components/ui';

interface DefectSummary {
  total?: number;
  open?: number;
  resolved?: number;
  critical?: number;
  blockers?: number;
  reopened?: number;
  mttr_hours?: number | null;
  aging_days?: number | null;
  by_severity?: Record<string, number>;
  by_state?: Record<string, number>;
}

interface DefectItem {
  id?: number;
  azure_id?: string;
  title?: string;
  severity?: string;
  priority?: string;
  state?: string;
  assigned_to?: string;
  iteration_name?: string | null;
  created_at?: string;
  resolved_at?: string | null;
}

export default function DefectsPage() {
  const s = useApi<DefectSummary>('/defects/summary');
  const l = useApi<{ items?: DefectItem[]; total?: number }>('/defects');

  if (s.loading || l.loading) return <Page title="Defects"><Loading /></Page>;
  if (s.error || l.error)
    return (
      <Page title="Defects">
        {s.error && <ErrorBanner message={s.error} />}
        {l.error && <ErrorBanner message={l.error} />}
      </Page>
    );

  const d = s.data || {};
  const severity = Object.entries(d.by_severity || {});

  return (
    <Page title="Defects" subtitle={`${d.total ?? 0} total · MTTR ${d.mttr_hours != null ? `${d.mttr_hours}h` : '—'}`}>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
        <Kpi label="Open" value={d.open ?? 0} />
        <Kpi label="Resolved" value={d.resolved ?? 0} tone="good" />
        <Kpi label="Critical" value={d.critical ?? 0} tone={Number(d.critical) > 0 ? 'bad' : undefined} />
        <Kpi label="Blockers" value={d.blockers ?? 0} tone={Number(d.blockers) > 0 ? 'bad' : undefined} />
        <Kpi label="Reopened" value={d.reopened ?? 0} tone="warn" />
        <Kpi label="Oldest age" value={d.aging_days != null ? `${d.aging_days}d` : '—'} tone="warn" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="By severity">
          <SeverityBars data={severity} />
        </Card>
        <Card title="By state">
          <StateList data={d.by_state || {}} />
        </Card>
      </div>

      <Card title="Defect list">
        <Table
          headers={['ID', 'Title', 'Severity', 'Priority', 'State', 'Assigned', 'Iteration', 'Created']}
          rows={(l.data?.items || []).map((def) => [
            <span key="id" className="font-mono text-xs">{def.azure_id}</span>,
            <span key="t">{def.title}</span>,
            <Status key="sev" value={def.severity} />,
            def.priority || '—',
            <Status key="state" value={def.state} />,
            def.assigned_to || '—',
            def.iteration_name || '—',
            <span key="c" className="text-xs text-gray-500">{(def.created_at || '').slice(0, 10)}</span>,
          ])}
        />
      </Card>
    </Page>
  );
}

function SeverityBars({ data }: { data: [string, number][] }) {
  if (!data.length) return <p className="py-4 text-center text-sm text-gray-400">No defects</p>;
  const max = Math.max(...data.map(([, n]) => n), 1);
  return (
    <div className="space-y-2">
      {data.map(([k, n]) => (
        <div key={k} className="flex items-center gap-2">
          <span className="w-24 text-xs text-gray-600">{k}</span>
          <div className="h-4 flex-1 overflow-hidden rounded bg-gray-200">
            <div className="h-full bg-brand" style={{ width: `${(n / max) * 100}%` }} />
          </div>
          <span className="text-xs font-semibold">{n}</span>
        </div>
      ))}
    </div>
  );
}

function StateList({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  if (!entries.length) return <p className="py-4 text-center text-sm text-gray-400">No data</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([k, n]) => (
        <span key={k} className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-700">
          {k}: <b>{n}</b>
        </span>
      ))}
    </div>
  );
}
