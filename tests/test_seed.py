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

"""Tests for amiss.seed: idempotent dummy data seeding."""

from unittest.mock import patch

from amiss.model import SDP, STP, Reservation, Segment


def _patch_session(db_session):
    """Route amiss.seed.Session (Session.begin()) to the test db_session."""
    mock = patch("amiss.seed.Session")
    mock_session_cls = mock.start()
    mock_session_cls.return_value.__enter__ = lambda _: db_session
    mock_session_cls.return_value.__exit__ = lambda *_: None
    mock_session_cls.begin.return_value.__enter__ = lambda _: db_session
    mock_session_cls.begin.return_value.__exit__ = lambda *_: None
    db_session.commit = lambda: None
    return mock


def _segments_on_sdp(sdp, segments):
    """Replicate spectrum_detail's match: segments whose sourceStp (minus ?vlan=) is an SDP STP."""
    want = {sdp.stpA.stpId, sdp.stpZ.stpId}
    return [s for s in segments if (s.sourceStp.split("?")[0] if "?" in s.sourceStp else s.sourceStp) in want]


class TestSeed:
    def test_seeds_full_topology(self, db_session):
        from amiss.seed import DUMMY_RESERVATIONS, DUMMY_SDPS, DUMMY_SEGMENTS, DUMMY_STPS, RESERVATION_SOURCE_STP, seed

        mock = _patch_session(db_session)
        try:
            seed()
        finally:
            mock.stop()

        assert db_session.query(STP).count() == len(DUMMY_STPS)
        assert db_session.query(SDP).count() == len(DUMMY_SDPS)
        assert db_session.query(Reservation).count() == len(DUMMY_RESERVATIONS)
        assert db_session.query(Segment).count() == len(DUMMY_SEGMENTS)

        # isSdpMember reflects SDP membership: the endpoint source STP is not a member.
        source_stp = db_session.query(STP).filter(STP.stpId == RESERVATION_SOURCE_STP).one()
        assert source_stp.isSdpMember is False
        assert db_session.query(STP).filter(STP.isSdpMember).count() == 4

        # Every segment resolves to a real parent reservation.
        reservation_ids = {r.id for r in db_session.query(Reservation).all()}
        assert all(s.reservation_id in reservation_ids for s in db_session.query(Segment).all())

        # Reservations link to real source/dest STPs and to at least one SDP.
        for reservation in db_session.query(Reservation).all():
            assert reservation.sourceStp is not None
            assert reservation.destStp is not None
            assert len(reservation.sdps) >= 1

    def test_segments_resolve_against_sdps_like_spectrum_view(self, db_session):
        """The seeded SDPs must surface the seeded segments the way spectrum_detail does."""
        from amiss.seed import seed

        mock = _patch_session(db_session)
        try:
            seed()
        finally:
            mock.stop()

        segments = db_session.query(Segment).all()
        moxy_sdp = db_session.query(SDP).filter(SDP.stpAId == _stp_id(db_session, "internet2.edu:2025:ana:manlan.moxy-1")).one()
        nea3r_sdp = db_session.query(SDP).filter(SDP.stpAId == _stp_id(db_session, "internet2.edu:2025:ana:manlan.netherlight-1")).one()

        # The MOXY link carries both MOXY reservations (4 segments: vlan 481 + vlan 139, both directions).
        assert len(_segments_on_sdp(moxy_sdp, segments)) == 4
        # The NEA3R link carries the one NEA3R cross-domain segment.
        assert len(_segments_on_sdp(nea3r_sdp, segments)) == 1
        # Every SDP surfaces at least one segment (no orphan links).
        for sdp in db_session.query(SDP).all():
            assert len(_segments_on_sdp(sdp, segments)) >= 1

    def test_is_idempotent(self, db_session):
        from amiss.seed import DUMMY_RESERVATIONS, DUMMY_SDPS, DUMMY_SEGMENTS, DUMMY_STPS, seed

        mock = _patch_session(db_session)
        try:
            seed()
            seed()
        finally:
            mock.stop()

        assert db_session.query(STP).count() == len(DUMMY_STPS)
        assert db_session.query(SDP).count() == len(DUMMY_SDPS)
        assert db_session.query(Reservation).count() == len(DUMMY_RESERVATIONS)
        assert db_session.query(Segment).count() == len(DUMMY_SEGMENTS)


def _stp_id(db_session, stp_id_str):
    return db_session.query(STP).filter(STP.stpId == stp_id_str).one().id
