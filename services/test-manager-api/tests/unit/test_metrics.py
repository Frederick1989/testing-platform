"""Metric-layer tests against the seeded demo dataset (deterministic)."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models.test import AcceptanceCriterion, Defect, TestResult
from app.services import coverage as coverage_svc
from app.services import defects as defects_svc
from app.services import flakiness as flakiness_svc
from app.services import risks as risks_svc
from app.services.readiness import list_ready_stories


def test_coverage_dimensions_are_consistent(seeded):
    with SessionLocal() as s:
        summary = coverage_svc.summarize(s)
        assert summary["requirement"] > 0
        assert 0 < summary["requirement"] <= 100
        assert 0 <= summary["execution"] <= 100
        assert summary["acceptance_criteria_total"] >= summary["acceptance_criteria_covered"]


def test_story_coverage_matches_per_story_view(seeded):
    with SessionLocal() as s:
        by_story = coverage_svc.story_coverage(s)
        assert by_story["covered"] <= by_story["total"]
        rows = [r for r in _story_rows(s)]
        if rows:
            assert max(r["coverage"] for r in rows) <= 100.0


def _story_rows(session):
    from app.models.azure import WorkItem

    for story in session.scalars(
        select(WorkItem).where(WorkItem.type == "User Story", WorkItem.is_active.is_(True))
    ):
        acs = [a for a in story.acceptance_criteria if a.is_active]
        covered = sum(1 for a in acs if a.status == "COVERED")
        yield {
            "coverage": round(covered / max(len(acs), 1) * 100, 1),
            "total": len(acs),
        }


def test_defect_metrics_derived(seeded):
    with SessionLocal() as s:
        summary = defects_svc.summary(s)
        total = s.scalar(select(func.count(Defect.id))) or 0
        assert summary["total"] == total
        assert summary["open"] + summary["resolved"] == total
        if summary["open"] > 0:
            assert summary["aging_days_avg"] is not None
            assert summary["oldest_open"] is not None
        assert set(summary["by_severity"]) <= {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_flakiness_detector_requires_min_runs(seeded):
    with SessionLocal() as s:
        strict = flakiness_svc.flaky_tests(s, min_runs=1000)
        assert strict["tests"] == []
        assert strict["count"] == 0


def test_flaky_tests_have_both_pass_and_fail_history(seeded):
    with SessionLocal() as s:
        data = flakiness_svc.flaky_tests(s, min_runs=3)
        for f in data["tests"]:
            assert f["passes"] > 0
            assert f["failures"] > 0
            assert f["passes"] + f["failures"] == f["runs"]


def test_regression_report_counts_are_integers(seeded):
    with SessionLocal() as s:
        report = flakiness_svc.regression_report(s)
        for key in ("new_failures", "recovered", "repeated_failures"):
            assert isinstance(report["counts"][key], int)
        assert isinstance(report["new_failures"], list)
        assert isinstance(report["repeated_failures"], list)


def test_risks_are_structured(seeded):
    with SessionLocal() as s:
        risks = risks_svc.compute_risks(s)
        for risk in risks:
            assert risk["category"] in ("coverage", "execution", "defects", "process")
            assert risk["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            assert risk["count"] >= 0


def test_ready_stories_meet_gates(seeded):
    with SessionLocal() as s:
        ready = list_ready_stories(s)
        for story in ready:
            assert story["status"] == "UAT_READY"


def test_every_active_ac_has_status(seeded):
    with SessionLocal() as s:
        invalid = s.scalars(
            select(AcceptanceCriterion).where(
                AcceptanceCriterion.is_active.is_(True),
                AcceptanceCriterion.status.notin_(
                    ["COVERED", "PARTIALLY_COVERED", "NOT_COVERED"]
                ),
            )
        ).all()
        assert invalid == []


def test_results_have_seeded_history(seeded):
    with SessionLocal() as s:
        count = s.scalar(select(func.count(TestResult.id))) or 0
        assert count > 0


def test_capacity_split_classifies_effort(seeded):
    from app.models.azure import WorkItem

    with SessionLocal() as s:
        split = coverage_svc.capacity_split(s)
        total = s.scalar(
            select(func.count(WorkItem.id)).where(
                WorkItem.type == "User Story", WorkItem.is_active.is_(True)
            )
        ) or 0
        assert split["total"] == total
        assert split["automated"] + split["manual"] + split["non_test"] == total
        assert split["automated_pct"] + split["manual_pct"] + split["non_test_pct"] == 100.0
        # demo stories classify deterministically by automation status / tags
        by_azure = {w.azure_id: w for w in s.scalars(
            select(WorkItem).where(WorkItem.azure_id.in_([1234, 1236, 1238]))
        )}
        from app.repositories import azure as az_repo

        assert az_repo.automation_status(by_azure[1234]) == "automated"
        assert az_repo.automation_status(by_azure[1236]) == "manual"
        assert az_repo.acceptance_test_required(by_azure[1238]) is False


def test_non_test_stories_excluded_from_coverage(seeded):
    from app.models.azure import WorkItem

    with SessionLocal() as s:
        total_raw = s.scalar(
            select(func.count(WorkItem.id)).where(
                WorkItem.type == "User Story", WorkItem.is_active.is_(True)
            )
        ) or 0
        # demo seeds 4 stories; the Acceptance-Test-Required=False one is excluded
        assert len(coverage_svc._stories(s)) == total_raw - 1


def test_automated_stories_missing_ac_detected(seeded):
    with SessionLocal() as s:
        missing = coverage_svc.automated_stories_missing_ac(s)
        assert missing["count"] == 0
        for item in missing["items"]:
            assert item["azure_id"]


def test_resolution_distribution_structure(seeded):
    with SessionLocal() as s:
        data = defects_svc.resolution_distribution(s)
        assert set(data) == {"count", "distribution", "stats", "slowest", "over_7d_pct"}
        assert data["count"] > 0
        assert len(data["distribution"]) == 6
        assert sum(b["count"] for b in data["distribution"]) == data["count"]
        assert data["stats"]["count"] == data["count"]
        assert len(data["slowest"]) <= 5
        assert 0 <= data["over_7d_pct"] <= 100
        assert data["stats"]["p50_hours"] <= data["stats"]["p95_hours"]


def test_open_aging_structure(seeded):
    with SessionLocal() as s:
        data = defects_svc.open_aging(s)
        assert set(data) == {"open", "buckets", "oldest", "over_7d", "over_7d_pct"}
        assert len(data["buckets"]) == 4
        assert sum(b["count"] for b in data["buckets"]) == data["open"]
        assert 0 <= data["over_7d_pct"] <= 100


def test_dashboard_payload_has_resolution_capacity_and_pain_points(seeded):
    from app.services import dashboard as dashboard_svc

    with SessionLocal() as s:
        summary = dashboard_svc.summary(s)
        assert "defect_resolution" in summary
        assert "open_defect_aging" in summary
        assert "capacity" in summary
        assert "missing_ac_stories" in summary
        assert "pain_points" in summary
        assert summary["pain_points"]
        assert "defect_trend" not in summary
        for point in summary["pain_points"]:
            assert point["level"] in ("critical", "warning", "info")
            assert point["title"] and point["detail"]
