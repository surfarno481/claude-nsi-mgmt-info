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

"""Tests for the spectrum detail view, now backed by the Segment DB table."""

from unittest.mock import patch

from fastui import components as c


def _patch_session(db_session):
    """Route amiss.frontend.spectrum.Session to the test db_session."""
    mock = patch("amiss.frontend.spectrum.Session")
    mock_session_cls = mock.start()
    mock_session_cls.return_value.__enter__ = lambda _: db_session
    mock_session_cls.return_value.__exit__ = lambda *_: None
    return mock


def _segment_table_data(components):
    """Return the data of the single c.Table inside the rendered page."""
    page = next(comp for comp in components if isinstance(comp, c.Page))
    tables = [comp for comp in page.components if isinstance(comp, c.Table)]
    assert len(tables) == 1
    return tables[0].data


class TestSpectrumDetail:
    def test_matches_segments_by_source_stp_stripping_vlan(
        self, db_session, stp_factory, sdp_factory, segment_factory
    ):
        from amiss.frontend.spectrum import spectrum_detail

        stp_a = stp_factory(stpId="internet2.edu:2025:ana:manlan.ps1")
        stp_z = stp_factory(stpId="surf.nl:2020:ana:netherlight.ps1")
        db_session.add(stp_a)
        db_session.add(stp_z)
        db_session.flush()

        sdp = sdp_factory(stpAId=stp_a.id, stpZId=stp_z.id)
        db_session.add(sdp)
        db_session.flush()

        db_session.add(segment_factory(connectionId="match-a", sourceStp="internet2.edu:2025:ana:manlan.ps1"))
        db_session.add(segment_factory(connectionId="match-z", sourceStp="surf.nl:2020:ana:netherlight.ps1?vlan=481"))
        db_session.add(segment_factory(connectionId="no-match", sourceStp="some.other:2025:stp"))
        db_session.flush()

        mock = _patch_session(db_session)
        try:
            result = spectrum_detail(sdp.id)
        finally:
            mock.stop()

        data = _segment_table_data(result)
        assert {segment.connectionId for segment in data} == {"match-a", "match-z"}

    def test_unknown_sdp_returns_not_found_page(self, db_session):
        from amiss.frontend.spectrum import spectrum_detail

        mock = _patch_session(db_session)
        try:
            result = spectrum_detail(9999)
        finally:
            mock.stop()

        # No Segment table is rendered for a missing SDP.
        page = next(comp for comp in result if isinstance(comp, c.Page))
        assert not [comp for comp in page.components if isinstance(comp, c.Table)]
