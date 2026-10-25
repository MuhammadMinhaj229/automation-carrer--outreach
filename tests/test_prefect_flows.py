"""
Unit and integration tests for ACIOS Prefect Orchestration Flows.
"""

import sys
from pathlib import Path
import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from acios.flows.daily_signal_scan import fetch_expansion_signals, filter_and_persist_signals
from acios.flows.weekly_enrichment import identify_target_organizations
from acios.core.repository import CareerRepository


def test_fetch_expansion_signals_task():
    signals = fetch_expansion_signals(["Green Tech", "AgriTech"])
    assert len(signals) >= 5
    assert all(s.score >= 50 for s in signals)
    assert any("Oman" in s.headline or "Sohar" in s.headline for s in signals)


def test_identify_target_organizations_task():
    orgs = identify_target_organizations(limit=3)
    assert isinstance(orgs, list)
    assert len(orgs) <= 3
