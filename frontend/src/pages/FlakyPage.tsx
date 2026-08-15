import { useApi } from '../api/client';
import { Card, Page, Status, ErrorBanner, Loading, Table } from '../components/ui';

interface FlakyItem {
  test_case_id?: number;
  key?: string | null;
  title?: string;
  runs?: number;
  passes?: number;
  failures?: number;
  last_status?: string;
  last_run_at?: string;
}

interface FlakyData {
  count?: number;
  min_runs?: number;
  tests?: FlakyItem[];
}

export default function FlakyPage() {
  const { data, error, loading } = useApi<FlakyData>('/flaky-tests');

  if (loading) return <Page title="Flaky Tests"><Loading /></Page>;
  if (error) return <Page title="Flaky Tests"><ErrorBanner message={error} /></Page>;

  const items = data?.tests || [];

  return (
    <Page title="Flaky Tests" subtitle={`${data?.count ?? 0} flaky test(s) (min ${data?.min_runs ?? 3} runs)`}>
      <Card>
        <Table
          headers={['Key', 'Title', 'Runs', 'Passes', 'Failures', 'Last status', 'Last run']}
          rows={items.map((f) => [
            <span key="k" className="font-mono text-xs">{f.key || `#${f.test_case_id}`}</span>,
            <span key="t">{f.title}</span>,
            f.runs ?? 0,
            <span key="p" className="text-green-700">{f.passes ?? 0}</span>,
            <span key="f" className="text-red-700">{f.failures ?? 0}</span>,
            <Status key="s" value={f.last_status} />,
            <span key="d" className="text-xs text-gray-500">{(f.last_run_at || '').slice(0, 19)}</span>,
          ])}
        />
      </Card>
    </Page>
  );
}
