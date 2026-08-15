import { useState } from 'react';
import { api, useApi, API_BASE } from '../api/client';
import { Card, Page, Status, ErrorBanner, Loading, Table } from '../components/ui';

interface ArchiveItem {
  id?: number;
  title?: string;
  sprint_name?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  generated_at?: string;
  status?: string;
  created_by?: string | null;
}

export default function ReportsPage() {
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);
  const latest = useApi<{ id?: number; title?: string; generated_at?: string; status?: string; snapshot?: unknown } | null>('/reports/latest');
  const archive = useApi<{ items?: ArchiveItem[] }>('/reports/archive');

  async function generate() {
    setGenerating(true);
    setGenMsg(null);
    try {
      const res = await api<{ job_id: string; status: string }>('/reports/generate', { method: 'POST' });
      setGenMsg(`Report generation queued (job ${res.job_id}). It will appear here once complete.`);
      setTimeout(() => {
        latest.refetch();
        archive.refetch();
      }, 3000);
    } catch (e) {
      setGenMsg(`Failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setGenerating(false);
    }
  }

  const latestData = latest.error ? null : latest.data;
  const latestArchive = archive.data?.items || [];

  return (
    <Page title="Reports" subtitle="Snapshotted UAT reports (HTML + PDF archive)">
      <Card title="Generate report">
        <div className="flex items-center gap-3">
          <button
            onClick={generate}
            disabled={generating}
            className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
          >
            {generating ? 'Queuing…' : 'Generate report'}
          </button>
          <span className="text-xs text-gray-500">Snapshot of the current sprint metrics into a versioned HTML/PDF archive.</span>
        </div>
        {genMsg && <p className="mt-2 text-sm text-gray-600">{genMsg}</p>}
      </Card>

      {(latest.loading || archive.loading) && <Loading />}
      {(latest.error || archive.error) && (
        <>
          {latest.error && <ErrorBanner message={latest.error} />}
          {archive.error && <ErrorBanner message={archive.error} />}
        </>
      )}

      {latestData && (
        <Card title="Latest report">
          <div className="flex items-center gap-4">
            <div>
              <div className="font-semibold">{latestData.title}</div>
              <div className="text-xs text-gray-500">
                Generated {latestData.generated_at ? String(latestData.generated_at).slice(0, 19) : '—'} ·{' '}
                <Status value={latestData.status} />
              </div>
            </div>
            <a
              href={`${API_BASE}/reports/archive/${latestData.id}/html`}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-brand underline-offset-2 hover:underline"
            >
              View HTML
            </a>
            <a
              href={`${API_BASE}/reports/archive/${latestData.id}/pdf`}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-brand underline-offset-2 hover:underline"
            >
              Download PDF
            </a>
          </div>
        </Card>
      )}

      <Card title={`Archive (${latestArchive.length})`}>
        <Table
          headers={['ID', 'Title', 'Sprint', 'Period', 'Generated', 'Status']}
          rows={latestArchive.map((a) => [
            <span key="id" className="font-mono text-xs">{a.id}</span>,
            <span key="t">
              {a.title}{' '}
              <a className="ml-1 text-xs text-brand underline-offset-2 hover:underline" target="_blank" rel="noreferrer" href={`${API_BASE}/reports/archive/${a.id}/html`}>
                html
              </a>
              {' '}
              <a className="text-xs text-brand underline-offset-2 hover:underline" target="_blank" rel="noreferrer" href={`${API_BASE}/reports/archive/${a.id}/pdf`}>
                pdf
              </a>
            </span>,
            a.sprint_name || '—',
            a.period_start ? `${String(a.period_start).slice(0, 10)} → ${String(a.period_end).slice(0, 10)}` : '—',
            <span key="g" className="text-xs text-gray-500">{a.generated_at ? String(a.generated_at).slice(0, 19) : '—'}</span>,
            <Status key="s" value={a.status} />,
          ])}
        />
      </Card>
    </Page>
  );
}
