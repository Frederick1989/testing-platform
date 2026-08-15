"""Import all models so Alembic autogenerate and Base.metadata see them."""
from app.models.analysis import (  # noqa: F401
    Agent,
    AgentJob,
    Notification,
    ReportArchive,
    TestGenerationCandidate,
    TestMatrixAnalysis,
)
from app.models.azure import (  # noqa: F401
    AzureComment,
    AzureSyncLog,
    Iteration,
    PullRequest,
    WorkItem,
)
from app.models.test import (  # noqa: F401
    AcceptanceCriterion,
    Defect,
    TestCase,
    TestDefectLink,
    TestImplementation,
    TestResult,
    TestRun,
    TestScenario,
    TestStoryLink,
)
