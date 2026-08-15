import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/ui';
import DashboardPage from './pages/DashboardPage';
import CoveragePage from './pages/CoveragePage';
import TestMatrixPage from './pages/TestMatrixPage';
import TestCasesPage from './pages/TestCasesPage';
import DefectsPage from './pages/DefectsPage';
import FlakyPage from './pages/FlakyPage';
import RisksPage from './pages/RisksPage';
import SprintsPage from './pages/SprintsPage';
import VelocityPage from './pages/VelocityPage';
import RegressionPage from './pages/RegressionPage';
import TestRunsPage from './pages/TestRunsPage';
import AgentsPage from './pages/AgentsPage';
import JobsPage from './pages/JobsPage';
import ReportsPage from './pages/ReportsPage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/coverage" element={<CoveragePage />} />
        <Route path="/test-matrix" element={<TestMatrixPage />} />
        <Route path="/test-cases" element={<TestCasesPage />} />
        <Route path="/defects" element={<DefectsPage />} />
        <Route path="/flaky" element={<FlakyPage />} />
        <Route path="/risks" element={<RisksPage />} />
        <Route path="/sprints" element={<SprintsPage />} />
        <Route path="/velocity" element={<VelocityPage />} />
        <Route path="/regression" element={<RegressionPage />} />
        <Route path="/test-runs" element={<TestRunsPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="*" element={<DashboardPage />} />
      </Routes>
    </Layout>
  );
}
