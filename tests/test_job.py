# Copyright 2024-2026 SURF.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for amiss.job: Job functions (mocked DB and HTTP)."""

from unittest.mock import MagicMock, call, patch

import pytest


class TestNsiPollDdsJob:
    @patch("amiss.job.dds_proxy_json_to_sdps")
    @patch("amiss.job.get_dds_proxy_sdps")
    @patch("amiss.job.update_stps")
    @patch("amiss.job.dds_proxy_json_to_stps")
    @patch("amiss.job.get_dds_proxy_stps")
    @patch("amiss.job.Session")
    def test_wipes_then_polls_proxy(
        self, mock_session_cls, mock_get_stps, mock_to_stps, mock_update_stps, mock_get_sdps, mock_to_sdps
    ):
        from amiss.job import nsi_poll_dds_job

        mock_session = MagicMock()
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_stps.return_value = b'[{"id": "x"}]'
        mock_to_stps.return_value = ["stp"]
        mock_get_sdps.return_value = b'[{"stpAId": "a", "stpZId": "z"}]'

        nsi_poll_dds_job()

        # Both tables wiped first (query(SDP).delete(), query(STP).delete())
        assert mock_session.query.call_count == 2
        mock_to_stps.assert_called_once_with([{"id": "x"}])
        mock_update_stps.assert_called_once_with(["stp"])
        mock_to_sdps.assert_called_once_with([{"stpAId": "a", "stpZId": "z"}])

    @patch("amiss.job.dds_proxy_json_to_sdps")
    @patch("amiss.job.get_dds_proxy_sdps")
    @patch("amiss.job.update_stps")
    @patch("amiss.job.dds_proxy_json_to_stps")
    @patch("amiss.job.get_dds_proxy_stps")
    @patch("amiss.job.Session")
    def test_skips_parsing_when_fetch_returns_none(
        self, mock_session_cls, mock_get_stps, mock_to_stps, mock_update_stps, mock_get_sdps, mock_to_sdps
    ):
        from amiss.job import nsi_poll_dds_job

        mock_session = MagicMock()
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        mock_get_stps.return_value = None
        mock_get_sdps.return_value = None

        nsi_poll_dds_job()

        assert mock_session.query.call_count == 2  # tables still wiped
        mock_to_stps.assert_not_called()
        mock_update_stps.assert_not_called()
        mock_to_sdps.assert_not_called()


class TestNsiPollAggJob:
    @patch("amiss.job.temp_pull_reservations_from_agg")
    @patch("amiss.job.update_segments")
    @patch("amiss.job.get_aggregator_reservations")
    def test_returns_early_when_no_data(self, mock_get, mock_update, mock_pull):
        from amiss.job import nsi_poll_agg_job

        mock_get.return_value = None
        nsi_poll_agg_job()
        mock_pull.assert_not_called()
        mock_update.assert_not_called()

    @patch("amiss.job.temp_pull_reservations_from_agg")
    @patch("amiss.job.update_segments")
    @patch("amiss.job.get_aggregator_reservations")
    def test_returns_on_invalid_json(self, mock_get, mock_update, mock_pull):
        from amiss.job import nsi_poll_agg_job

        mock_get.return_value = b"not json"
        nsi_poll_agg_job()
        mock_pull.assert_not_called()
        mock_update.assert_not_called()

    @patch("amiss.job.temp_pull_reservations_from_agg")
    @patch("amiss.job.update_segments")
    @patch("amiss.job.get_aggregator_reservations")
    def test_returns_when_no_reservations_key(self, mock_get, mock_update, mock_pull):
        from amiss.job import nsi_poll_agg_job

        mock_get.return_value = b'{"other": []}'
        nsi_poll_agg_job()
        mock_pull.assert_not_called()
        mock_update.assert_not_called()

    @patch("amiss.job.temp_pull_reservations_from_agg")
    @patch("amiss.job.update_segments")
    @patch("amiss.job.get_aggregator_reservations")
    def test_pulls_reservations_then_updates_segments(self, mock_get, mock_update, mock_pull):
        from amiss.job import nsi_poll_agg_job

        mock_get.return_value = (
            b'{"reservations": ['
            b'{"connectionId": "c1", "segments": [{"order": 0}]},'
            b'{"connectionId": "c2"},'  # no segments -> skipped by update_segments
            b'{"segments": [{"order": 0}]}'  # no connectionId -> skipped by update_segments
            b']}'
        )
        nsi_poll_agg_job()

        # The full reservations list is pulled into the DB before segment sync.
        mock_pull.assert_called_once_with(
            [
                {"connectionId": "c1", "segments": [{"order": 0}]},
                {"connectionId": "c2"},
                {"segments": [{"order": 0}]},
            ]
        )
        mock_update.assert_called_once_with("c1", [{"order": 0}])


class TestNsiPollSources:
    @patch("amiss.job.nsi_poll_agg_job")
    @patch("amiss.job.nsi_poll_dds_job")
    def test_calls_dds_then_agg(self, mock_dds, mock_agg):
        from amiss.job import nsi_poll_sources

        manager = MagicMock()
        manager.attach_mock(mock_dds, "dds")
        manager.attach_mock(mock_agg, "agg")

        nsi_poll_sources()

        # Both sources polled once, DDS before the aggregator.
        assert manager.mock_calls == [call.dds(), call.agg()]
