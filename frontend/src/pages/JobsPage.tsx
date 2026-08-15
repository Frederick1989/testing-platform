import { useApi } from '../api/client';
import { Card, Page, Status, ErrorBanner, Loading, Table } from '../components/ui';

interface Job {
  job_id?: string;
  job_type?: string;
  status?: string;
  trigger?: string;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export default function JobsPage() {
  const { data, error, loading } = useApi<{ items?: Job[] }>('/jobs');

  if (loading) return <Page title="Jobs"><Loading /></Page>;
  if (error) return <Page title="Jobs"><ErrorBanner message={error} /></Page>;

  const items = data?.items || [];

  return (
    <Page title="Jobs" subtitle="Async job queue — sync, analysis, reporting">
      <Card>
        <Table
          headers={['Job ID', 'Type', 'Trigger', 'Status', 'Created', 'Finished', 'Error']}
          rows={items.map((j) => [
            <span key="id" className="font-mono text-xs">{j.job_id}</span>,
            j.job_type || '—',
            j.trigger || '—',
            <Status key="s" value={j.status} />,
            <span key="c" className="text-xs text-gray-500">{(j.created_at || '').slice(0, 19)}</span>,
            <span key="f" className="text-xs text-gray-500">{j.finished_at ? String(j.finished_at).slice(0, 19) : '—'}</span>,
            <span key="e" className="max-w-[220px] truncate text-xs text-red-700" title={j.error || undefined}>
              {j.error || '—'}
            </span>,
          ])}
        />
      </Card>
    </Page>
  );
}
