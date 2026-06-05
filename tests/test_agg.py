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

"""Tests for amiss.agg: aggregator proxy helpers (mocked HTTP)."""

from unittest.mock import patch

from pydantic import HttpUrl


class TestGetAggregatorReservations:
    @patch("amiss.agg.nsi_util_get_json")
    def test_appends_reservations_path_and_detail_full(self, mock_get_json):
        from amiss.agg import get_aggregator_reservations

        mock_get_json.return_value = b'{"reservations": []}'

        result = get_aggregator_reservations(HttpUrl("http://agg.example/aggregator-proxy/"))

        mock_get_json.assert_called_once()
        called_url, called_params = mock_get_json.call_args.args
        assert str(called_url) == "http://agg.example/aggregator-proxy/reservations"
        assert called_params == {"detail": "full"}
        # Raw bytes are passed straight through from nsi_util_get_json.
        assert result == b'{"reservations": []}'

    @patch("amiss.agg.nsi_util_get_json")
    def test_handles_base_url_without_trailing_slash(self, mock_get_json):
        from amiss.agg import get_aggregator_reservations

        get_aggregator_reservations(HttpUrl("http://agg.example/aggregator-proxy"))

        called_url, _ = mock_get_json.call_args.args
        # No double slash, prefix preserved.
        assert str(called_url) == "http://agg.example/aggregator-proxy/reservations"

    @patch("amiss.agg.nsi_util_get_json")
    def test_returns_none_when_request_fails(self, mock_get_json):
        from amiss.agg import get_aggregator_reservations

        mock_get_json.return_value = None

        assert get_aggregator_reservations(HttpUrl("http://agg.example/")) is None
