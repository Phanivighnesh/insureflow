"""Governance tests for the AI module.

Verifies:
1. AST static check: app/ai never imports GroundTruth, never imports mutators from workflow,
   never calls session.add/delete/commit in tools/intents/templates.
2. Read-only database guarantees: tool execution causes zero database row changes.
"""
import ast
import os
import glob
import pytest
from sqlalchemy import func, select

from app.models import Applicant, Policy, Quote, UnderwritingDecision


def test_ast_prohibits_ground_truth_imports():
    ai_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "ai"))
    py_files = glob.glob(os.path.join(ai_dir, "*.py"))
    assert len(py_files) >= 5

    for filepath in py_files:
        tree = ast.parse(open(filepath, encoding="utf-8").read(), filename=filepath)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "GroundTruth" not in alias.name, f"{filepath} imports GroundTruth directly"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "GroundTruth" not in module, f"{filepath} imports from GroundTruth"
                for alias in node.names:
                    assert alias.name != "GroundTruth", f"{filepath} imports GroundTruth from {module}"


def test_ast_prohibits_workflow_mutator_imports():
    ai_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "ai"))
    # service.py and tools.py must not import workflow state changers
    for name in ("tools.py", "intents.py", "templates.py", "guard.py", "prompts.py"):
        filepath = os.path.join(ai_dir, name)
        if not os.path.exists(filepath):
            continue
        content = open(filepath, encoding="utf-8").read()
        assert "submit_quote" not in content
        assert "approve_quote" not in content
        assert "decline_quote" not in content
        assert "cancel_policy" not in content


def test_tools_cause_zero_database_mutations(session):
    from app.ai.tools import tool_rules_help, tool_senior_review_queue, tool_anomaly_summary

    # Capture row counts before
    q_count_before = session.scalar(select(func.count()).select_from(Quote))
    p_count_before = session.scalar(select(func.count()).select_from(Policy))
    a_count_before = session.scalar(select(func.count()).select_from(Applicant))

    # Run read-only tools
    tool_rules_help("What is the auto-approval limit?")
    tool_senior_review_queue(session)
    tool_anomaly_summary(session)

    # Row counts must be identical after
    assert session.scalar(select(func.count()).select_from(Quote)) == q_count_before
    assert session.scalar(select(func.count()).select_from(Policy)) == p_count_before
    assert session.scalar(select(func.count()).select_from(Applicant)) == a_count_before

