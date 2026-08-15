import { useApi } from '../api/client';
import { Card, Page, Status, ErrorBanner, Loading, Table } from '../components/ui';

interface RegressionData {
  new_failures?: { key?: string | null; title?: string; last_status?: string; previous_status?: string }[];
  recovered?: { key?: string | null; title?: string; last_status?: string; previous_status?: string }[];
  repeated_failures?: { key?: string | null; title?: string; failure_count?: number; runs?: number; failure_rate?: number }[];
  counts?: { new_failures?: number; recovered?: number; repeated_failures?: number };
}

export default function RegressionPage() {
  const { data, error, loading } = useApi<RegressionData>('/regression');

  if (loading) return <Page title="Regression"><Loading /></Page>;
  if (error) return <Page title="Regression"><ErrorBanner message={error} /></Page>;

  const c = data?.counts || {};
  const title = (t: string | null | undefined) => t || '(unknown test)';

  return (
    <Page title="Regression" subtitle="New failures, recovered tests and repeatedly failing tests">
      <div className="grid grid-cols-3 gap-4">
        <Card title="New failures">
          <div className="text-2xl font-bold text-red-700">{c.new_failures ?? 0}</div>
        </Card>
        <Card title="Recovered">
          <div className="text-2xl font-bold text-green-700">{c.recovered ?? 0}</div>
        </Card>
        <Card title="Repeated failures">
          <div className="text-2xl font-bold text-yellow-700">{c.repeated_failures ?? 0}</div>
        </Card>
      </div>

      <Card title="New failures (last run failed, previous passed)">
        <Table
          headers={['Test', 'Previous', 'Last']}
          empty="No new failures"
          rows={(data?.new_failures || []).map((f) => [
            <span key="t">{title(f.title)} <span className="font-mono text-xs text-gray-400">{f.key}</span></span>,
            <Status key="p" value={f.previous_status} />,
            <Status key="l" value={f.last_status} />,
          ])}
        />
      </Card>

      <Card title="Recovered (last run passed, previous failed)">
        <Table
          headers={['Test', 'Previous', 'Last']}
          empty="None recovered"
          rows={(data?.recovered || []).map((f) => [
            <span key="t">{title(f.title)} <span className="font-mono text-xs text-gray-400">{f.key}</span></span>,
            <Status key="p" value={f.previous_status} />,
            <Status key="l" value={f.last_status} />,
          ])}
        />
      </Card>

      <Card title="Repeatedly failing (≥3 failures)">
        <Table
          headers={['Test', 'Failures', 'Runs', 'Failure rate']}
          empty="No repeated failures"
          rows={(data?.repeated_failures || []).map((f) => [
            <span key="t">{title(f.title)} <span className="font-mono text-xs text-gray-400">{f.key}</span></span>,
            <span key="f" className="text-red-700">{f.failure_count ?? 0}</span>,
            f.runs ?? 0,
            <span key="r">{f.failure_rate ?? 0}%</span>,
          ])}
        />
      </Card>
    </Page>
  );
}
