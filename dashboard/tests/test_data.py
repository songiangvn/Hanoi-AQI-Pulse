"""Tests for src/data.py — data loading, column normalization, AQI utilities."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure dashboard root is on the path
DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
if str(DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_ROOT))

from src.data import DataBundle, load_bundle, _normalize_columns
from src.utils import aqi_advisory, aqi_category, aqi_color, metric_title


PROJECT_ROOT = DASHBOARD_ROOT.parent
DATA_ROOT = PROJECT_ROOT / "data"


class TestAqiCategory:
    def test_good(self):
        assert aqi_category(30) == "Good"

    def test_moderate(self):
        assert aqi_category(75) == "Moderate"

    def test_usg(self):
        assert aqi_category(120) == "USG"

    def test_unhealthy(self):
        assert aqi_category(180) == "Unhealthy"

    def test_very_unhealthy(self):
        assert aqi_category(250) == "Very Unhealthy"

    def test_hazardous(self):
        assert aqi_category(350) == "Hazardous"

    def test_boundary_50(self):
        assert aqi_category(50) == "Good"

    def test_none(self):
        assert aqi_category(None) == "Unknown"

    def test_nan(self):
        assert aqi_category(float("nan")) == "Unknown"


class TestAqiColor:
    def test_returns_hex(self):
        color = aqi_color(75)
        assert color.startswith("#")
        assert len(color) == 7

    def test_none_returns_grey(self):
        assert aqi_color(None) == "#7a8792"


class TestAqiAdvisory:
    def test_good(self):
        assert "safe" in aqi_advisory(30).lower()

    def test_hazardous(self):
        assert "indoors" in aqi_advisory(350).lower()

    def test_unknown(self):
        assert "unavailable" in aqi_advisory(None).lower()


class TestMetricTitle:
    def test_pm25(self):
        assert metric_title("pm25") == "PM2.5"

    def test_aqi(self):
        assert metric_title("aqi") == "AQI"


class TestNormalizeColumns:
    def test_lowercases(self):
        df = pd.DataFrame({"Local Time": [1], "PM2.5": [10]})
        out = _normalize_columns(df)
        assert "local_time" in out.columns
        assert "pm2.5" in out.columns

    def test_strips_whitespace(self):
        df = pd.DataFrame({" Name ": ["a"]})
        out = _normalize_columns(df)
        assert "name" in out.columns


class TestLoadBundle:
    @pytest.fixture(scope="class")
    def bundle(self):
        return load_bundle(DATA_ROOT)

    def test_city_hourly_not_empty(self, bundle):
        assert not bundle.city_hourly.empty

    def test_city_has_local_time(self, bundle):
        assert "local_time" in bundle.city_hourly.columns

    def test_city_has_aqi(self, bundle):
        assert "aqi" in bundle.city_hourly.columns

    def test_district_daily_not_empty(self, bundle):
        assert not bundle.district_daily.empty

    def test_district_has_time(self, bundle):
        assert "time" in bundle.district_daily.columns

    def test_district_has_district_col(self, bundle):
        assert "district" in bundle.district_daily.columns

    def test_district_has_30_districts(self, bundle):
        n = bundle.district_daily["district"].nunique()
        assert n == 30, f"Expected 30 districts, got {n}"
