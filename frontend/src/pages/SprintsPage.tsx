import { useApi } from '../api/client';
import { Card, Page, ErrorBanner, Loading, Table } from '../components/ui';

interface SprintSummary {
  id?: number;
  name?: string;
  state?: string;
  start_date?: string | null;
  finish_date?: string | null;
  is_current?: boolean;
}

export default function SprintsPage() {
  const { data, error, loading } = useApi<{ items?: SprintSummary[] }>('/sprints');

  if (loading) return <Page title="Sprints"><Loading /></Page>;
  if (error) return <Page title="Sprints"><ErrorBanner message={error} /></Page>;

  const items = data?.items || [];

  return (
    <Page title="Sprints" subtitle={`${items.length} iterations`}>
      <Card>
        <Table
          headers={['Sprint', 'State', 'Start', 'Finish', 'Current']}
          rows={items.map((s) => [
            <span key="n">{s.name} {s.is_current && <span className="ml-1 rounded bg-brand px-1.5 py-0.5 text-[10px] text-white">CURRENT</span>}</span>,
            s.state || '—',
            s.start_date ? String(s.start_date).slice(0, 10) : '—',
            s.finish_date ? String(s.finish_date).slice(0, 10) : '—',
            s.is_current ? <span key="c">Yes</span> : <span key="c" className="text-gray-400">No</span>,
          ])}
        />
      </Card>
    </Page>
  );
}
