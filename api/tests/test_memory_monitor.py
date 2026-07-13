"""Tests for memory_monitor.memory_usage_ratio (BUG-023).

Pure function -- file reads are mocked, no real cgroup filesystem needed.
"""

from unittest.mock import patch

from src.services.memory_monitor import memory_usage_ratio


class TestMemoryUsageRatio:
    def test_computes_ratio(self):
        with patch("src.services.memory_monitor._CGROUP_CURRENT") as mock_current, \
             patch("src.services.memory_monitor._CGROUP_MAX") as mock_max:
            mock_current.read_text.return_value = "4294967296"  # 4Gi
            mock_max.read_text.return_value = "8589934592"  # 8Gi
            assert memory_usage_ratio() == 0.5

    def test_unlimited_cgroup_returns_none(self):
        with patch("src.services.memory_monitor._CGROUP_CURRENT") as mock_current, \
             patch("src.services.memory_monitor._CGROUP_MAX") as mock_max:
            mock_current.read_text.return_value = "1000000"
            mock_max.read_text.return_value = "max"
            assert memory_usage_ratio() is None

    def test_missing_files_return_none(self):
        with patch("src.services.memory_monitor._CGROUP_CURRENT") as mock_current:
            mock_current.read_text.side_effect = OSError("no such file")
            assert memory_usage_ratio() is None

    def test_malformed_value_returns_none(self):
        with patch("src.services.memory_monitor._CGROUP_CURRENT") as mock_current, \
             patch("src.services.memory_monitor._CGROUP_MAX") as mock_max:
            mock_current.read_text.return_value = "not-a-number"
            mock_max.read_text.return_value = "8589934592"
            assert memory_usage_ratio() is None

    def test_zero_limit_returns_none(self):
        with patch("src.services.memory_monitor._CGROUP_CURRENT") as mock_current, \
             patch("src.services.memory_monitor._CGROUP_MAX") as mock_max:
            mock_current.read_text.return_value = "0"
            mock_max.read_text.return_value = "0"
            assert memory_usage_ratio() is None
