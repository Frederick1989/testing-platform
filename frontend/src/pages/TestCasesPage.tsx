import { useApi } from '../api/client';
import { Card, Page, Status, ErrorBanner, Loading, Table } from '../components/ui';

interface TestCase {
  id?: number;
  key?: string;
  title?: string;
  description?: string;
  priority?: string;
  suggested_framework?: string;
  status?: string;
  source?: string;
  linked_story_ids?: number[];
  linked_ac_ids?: number[];
}

export default function TestCasesPage() {
  const { data, error, loading } = useApi<{ items?: TestCase[]; total?: number }>('/test-cases');

  if (loading) return <Page title="Test Cases"><Loading /></Page>;
  if (error) return <Page title="Test Cases"><ErrorBanner message={error} /></Page>;

  const items = data?.items || [];

  return (
    <Page title="Test Cases" subtitle={`${data?.total ?? items.length} cases`}>
      <Card>
        <Table
          headers={['Key', 'Title', 'Framework', 'Priority', 'Status', 'Source', 'Links']}
          rows={items.map((tc) => [
            <span key="k" className="font-mono text-xs">{tc.key}</span>,
            <span key="t">{tc.title}</span>,
            tc.suggested_framework || '—',
            tc.priority || '—',
            <Status key="s" value={tc.status} />,
            tc.source || '—',
            <span key="l" className="text-xs text-gray-500">{tc.linked_story_ids?.length ?? 0} story{(tc.linked_story_ids?.length ?? 0) === 1 ? '' : 's'}</span>,
          ])}
        />
      </Card>
    </Page>
  );
}
