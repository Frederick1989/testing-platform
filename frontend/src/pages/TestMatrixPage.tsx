import { useApi } from '../api/client';
import { Card, Page, Status, ErrorBanner, Loading, Table } from '../components/ui';

interface MatrixRow {
  work_item_id?: number;
  azure_id?: string;
  title?: string;
  iteration?: string;
  state?: string;
  requirement?: string;
  test_cases?: { key?: string; title?: string; status?: string }[];
  covered_ac?: number;
  total_ac?: number;
  status?: string;
}

export default function TestMatrixPage() {
  const { data, error, loading } = useApi<{ items?: MatrixRow[]; total?: number }>('/test-matrix');

  if (loading) return <Page title="Test Matrix"><Loading /></Page>;
  if (error) return <Page title="Test Matrix"><ErrorBanner message={error} /></Page>;

  return (
    <Page title="Test Matrix" subtitle="Requirement-to-test traceability matrix">
      <Card title={`Stories (${data?.total ?? (data?.items || []).length})`}>
        <div className="space-y-6">
          {(data?.items || []).map((row) => (
            <div key={row.work_item_id} className="rounded border border-gray-100 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{row.title}</span>
                <span className="font-mono text-xs text-gray-400">{row.azure_id}</span>
                <Status value={row.status} />
                <span className="text-xs text-gray-500">
                  {row.covered_ac ?? 0} / {row.total_ac ?? 0} AC covered
                </span>
              </div>
              <div className="mt-1 text-xs text-gray-500">
                {row.requirement || '—'} · {row.iteration || 'no iteration'} · {row.state}
              </div>
              <Table
                headers={['Test case', 'Status']}
                empty="No linked test cases"
                rows={(row.test_cases || []).map((tc) => [
                  <span key="k" className="font-mono text-xs">{tc.key}</span>,
                  <span key="t" className="text-xs">{tc.title}</span>,
                  <Status key="s" value={tc.status} />,
                ])}
              />
            </div>
          ))}
        </div>
      </Card>
    </Page>
  );
}
