import { useApi } from '../api/client';
import { Card, Page, Status, ErrorBanner, Loading, Table } from '../components/ui';

interface TestRun {
  run_id?: string;
  framework?: string;
  environment?: string;
  branch?: string;
  commit_sha?: string;
  status?: string;
  total?: number;
  passed?: number;
  failed?: number;
  skipped?: number;
  flaky?: number;
  error_count?: number;
  started_at?: string;
  completed_at?: string | null;
  duration_ms?: number | null;
  report_location?: string | null;
}

export default function TestRunsPage() {
  const { data, error, loading } = useApi<{ items?: TestRun[] }>('/test-runs');

  if (loading) return <Page title="Test Runs"><Loading /></Page>;
  if (error) return <Page title="Test Runs"><ErrorBanner message={error} /></Page>;

  const fmtDur = (ms?: number | null) => (ms == null ? '—' : `${(ms / 1000).toFixed(1)}s`);

  return (
    <Page title="Test Runs" subtitle="API (pytest) and web (Playwright) framework executions">
      <Card>
        <Table
          headers={['Run ID', 'Framework', 'Env', 'Branch', 'Status', 'Passed', 'Failed', 'Skipped', 'Duration', 'Started']}
          rows={(data?.items || []).map((r) => [
            <span key="id" className="font-mono text-xs">{r.run_id}</span>,
            r.framework || '—',
            r.environment || '—',
            r.branch || '—',
            <Status key="s" value={r.status} />,
            <span key="p" className="text-green-700">{r.passed ?? 0}</span>,
            <span key="f" className="text-red-700">{r.failed ?? 0}</span>,
            r.skipped ?? 0,
            fmtDur(r.duration_ms),
            <span key="st" className="text-xs text-gray-500">{(r.started_at || '').slice(0, 19)}</span>,
          ])}
        />
      </Card>
    </Page>
  );
}
