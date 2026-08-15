import { useApi, api } from '../api/client';
import { Card, Page, Status, ErrorBanner, Loading, Table } from '../components/ui';

interface Agent {
  name?: string;
  schedule?: string;
  enabled?: boolean;
  last_run_at?: string | null;
  last_status?: string | null;
  run_count?: number;
  last_error?: string | null;
}

export default function AgentsPage() {
  const { data, error, loading, refetch } = useApi<{ items?: Agent[] }>('/agents');

  async function runAgent(name: string) {
    await api(`/agents/${name}/run`, { method: 'POST' });
    setTimeout(refetch, 1500);
  }

  if (loading) return <Page title="Agents"><Loading /></Page>;
  if (error) return <Page title="Agents"><ErrorBanner message={error} /></Page>;

  const items = data?.items || [];

  return (
    <Page title="Agents" subtitle="Automated UAT agents — coverage sync, analysis, reporting">
      <Card>
        <Table
          headers={['Agent', 'Schedule', 'Enabled', 'Run count', 'Last status', 'Last run', '']}
          rows={items.map((a) => [
            <span key="n" className="font-semibold">{a.name}</span>,
            a.schedule || '—',
            a.enabled ? <span key="e" className="text-green-700">Enabled</span> : <span key="e" className="text-gray-400">Disabled</span>,
            a.run_count ?? 0,
            <Status key="s" value={a.last_status} />,
            <span key="d" className="text-xs text-gray-500">{a.last_run_at ? String(a.last_run_at).slice(0, 19) : '—'}</span>,
            <button
              key="btn"
              onClick={() => runAgent(a.name || '')}
              className="rounded bg-brand px-2 py-1 text-xs font-medium text-white hover:bg-brand-dark"
            >
              Run now
            </button>,
          ])}
        />
      </Card>
    </Page>
  );
}
