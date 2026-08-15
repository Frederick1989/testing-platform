import { useApi } from '../api/client';
import { Card, Page, ErrorBanner, Loading } from '../components/ui';

interface RiskItem {
  category?: string;
  severity?: string;
  title?: string;
  description?: string;
  count?: number;
  items?: { title?: string; story?: string; criterion?: string; azure_id?: string }[];
}

interface RisksResponse {
  items: RiskItem[];
}

export default function RisksPage() {
  const { data, error, loading } = useApi<RisksResponse>('/risks');

  if (loading) return <Page title="Risks"><Loading /></Page>;
  if (error) return <Page title="Risks"><ErrorBanner message={error} /></Page>;

  const risks = data?.items || [];
  const sevColor: Record<string, string> = {
    CRITICAL: 'bg-red-600 text-white',
    HIGH: 'bg-red-100 text-red-800',
    MEDIUM: 'bg-yellow-100 text-yellow-800',
    LOW: 'bg-green-100 text-green-800',
  };

  return (
    <Page title="Risks" subtitle={`${risks.length} active risk(s)`}>
      <div className="space-y-4">
        {risks.map((r, i) => (
          <Card key={i}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`rounded px-2 py-0.5 text-xs font-semibold ${sevColor[r.severity || 'LOW'] || sevColor.LOW}`}>
                    {r.severity || 'LOW'}
                  </span>
                  <span className="text-xs uppercase text-gray-400">{r.category}</span>
                </div>
                <h3 className="mt-2 m-0 text-sm font-semibold">{r.title}</h3>
                <p className="m-0 mt-1 text-sm text-gray-500">{r.description}</p>
              </div>
              <span className="text-2xl font-bold text-gray-300">{r.count ?? 0}</span>
            </div>
            {r.items && r.items.length > 0 && (
              <ul className="mt-3 max-h-48 space-y-1 overflow-y-auto border-t border-gray-100 pt-2">
                {r.items.map((it, j) => (
                  <li key={j} className="text-xs text-gray-600">
                    {it.azure_id || it.story ? <span className="font-mono text-gray-400">{it.azure_id || it.story} · </span> : null}
                    {it.criterion || it.title}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ))}
      </div>
    </Page>
  );
}
