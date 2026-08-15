import { useApi } from '../api/client';
import { Card, Kpi, Page, Status, ErrorBanner, Loading, Percent, Table } from '../components/ui';

interface Summary {
  requirement?: number;
  story?: number;
  automation?: number;
  execution?: number;
  acceptance_criteria_total?: number;
  acceptance_criteria_covered?: number;
  stories_total?: number;
  stories_covered?: number;
  test_cases_total?: number;
  test_cases_automated?: number;
  executed_tests?: number;
  latest_run?: string | null;
}

interface ByStory {
  items?: { azure_id?: string; title?: string; iteration?: string; acceptance_criteria_total?: number; acceptance_criteria_covered?: number; coverage?: number; status?: string }[];
}

interface Gaps {
  uncovered_acceptance_criteria?: { id: number; work_item_id?: number; text?: string; status?: string }[];
  unexecuted_stories?: { azure_id?: string; title?: string }[];
  counts?: Record<string, number>;
}

export default function CoveragePage() {
  const s = useApi<Summary>('/coverage/summary');
  const byStory = useApi<ByStory>('/coverage/by-story');
  const gaps = useApi<Gaps>('/coverage/gaps');

  if (s.loading || byStory.loading || gaps.loading) return <Page title="Coverage"><Loading /></Page>;
  if (s.error || byStory.error || gaps.error)
    return (
      <Page title="Coverage">
        {s.error && <ErrorBanner message={s.error} />}
        {byStory.error && <ErrorBanner message={byStory.error} />}
        {gaps.error && <ErrorBanner message={gaps.error} />}
      </Page>
    );

  const d = s.data || {};
  return (
    <Page title="Coverage" subtitle="Requirements, stories, automation and execution coverage">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Kpi label="Requirement (AC)" value={`${d.requirement ?? 0}%`} sub={`${d.acceptance_criteria_covered ?? 0} / ${d.acceptance_criteria_total ?? 0} criteria`} tone="good" />
        <Kpi label="Stories" value={`${d.story ?? 0}%`} sub={`${d.stories_covered ?? 0} / ${d.stories_total ?? 0} stories`} tone="good" />
        <Kpi label="Automation" value={`${d.automation ?? 0}%`} sub={`${d.test_cases_automated ?? 0} / ${d.test_cases_total ?? 0} automated`} tone="warn" />
        <Kpi label="Execution (30d)" value={`${d.execution ?? 0}%`} sub={`${d.executed_tests ?? 0} tests executed`} tone="warn" />
      </div>

      <Card title="Coverage by story">
        <Table
          headers={['Story', 'Iteration', 'AC covered', 'Coverage', 'Status']}
          rows={(byStory.data?.items || []).map((row) => [
            <span key="t" className="font-medium">{row.title} <span className="text-xs text-gray-400">{row.azure_id}</span></span>,
            row.iteration || '—',
            `${row.acceptance_criteria_covered ?? 0} / ${row.acceptance_criteria_total ?? 0}`,
            <Percent key="p" value={row.coverage ?? 0} />,
            <Status key="s" value={row.status} />,
          ])}
        />
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Uncovered acceptance criteria" action={<span className="text-xs text-gray-400">{gaps.data?.counts?.['uncovered_acceptance_criteria'] ?? (gaps.data?.uncovered_acceptance_criteria || []).length} gaps</span>}>
          <Table
            headers={['AC', 'Status']}
            empty="No uncovered criteria"
            rows={(gaps.data?.uncovered_acceptance_criteria || []).map((a) => [
              <span key="t">{a.text}</span>,
              <Status key="s" value={a.status} />,
            ])}
          />
        </Card>
        <Card title="Stories without execution" action={<span className="text-xs text-gray-400">{gaps.data?.counts?.['unexecuted_stories'] ?? (gaps.data?.unexecuted_stories || []).length} stories</span>}>
          <Table
            headers={['Story']}
            empty="All stories executed"
            rows={(gaps.data?.unexecuted_stories || []).map((st) => [
              <span key="t">{st.title} <span className="text-xs text-gray-400">{st.azure_id}</span></span>,
            ])}
          />
        </Card>
      </div>
    </Page>
  );
}
