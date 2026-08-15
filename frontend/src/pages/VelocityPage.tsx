import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend,
} from 'recharts';
import { useApi } from '../api/client';
import { Card, Page, ErrorBanner, Loading } from '../components/ui';

interface VelocityItem {
  sprint?: string;
  committed?: number;
  completed?: number;
  velocity?: number;
}

export default function VelocityPage() {
  const { data, error, loading } = useApi<{ items?: VelocityItem[] }>('/velocity');

  if (loading) return <Page title="Velocity"><Loading /></Page>;
  if (error) return <Page title="Velocity"><ErrorBanner message={error} /></Page>;

  const items = data?.items || [];

  return (
    <Page title="Velocity" subtitle="Committed vs completed stories per sprint">
      <Card>
        {items.length === 0 ? (
          <p className="py-10 text-center text-sm text-gray-400">No velocity data</p>
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={items} barGap={4}>
                <XAxis dataKey="sprint" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="committed" fill="#9ca3af" name="Committed" />
                <Bar dataKey="completed" fill="#0f4c81" name="Completed" />
                <Bar dataKey="velocity" fill="#16a34a" name="Velocity" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
      <Card>
        <ul className="m-0 list-inside list-disc space-y-1 text-sm text-gray-700">
          {items.map((v) => (
            <li key={v.sprint}>
              <b>{v.sprint}</b>: committed {v.committed ?? 0}, completed {v.completed ?? 0}, velocity{' '}
              {v.velocity ?? 0}
            </li>
          ))}
        </ul>
      </Card>
    </Page>
  );
}
