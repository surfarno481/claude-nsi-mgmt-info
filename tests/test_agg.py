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
from uuid import UUID, uuid4

from pydantic import HttpUrl

from amiss.model import STP, Reservation, Segment


def _segdict(connectionId="child-seg-0", order=0, capacity=1000, sourceSTP="src?vlan=1", destSTP="dst?vlan=2", status="ACTIVATED"):
    return {
        "order": order,
        "connectionId": connectionId,
        "providerNSA": "urn:ogf:network:west.example.net:2025:nsa:supa",
        "serviceType": "EVTS.A-GOLE",
        "capacity": capacity,
        "sourceSTP": sourceSTP,
        "destSTP": destSTP,
        "status": status,
    }


def _resdict(
    connectionId="9adfed42-fa58-4d26-bf74-9f5e14ab2281",
    sourceSTP="urn:ogf:network:example:2024:topo:ps1?vlan=100",
    destSTP="urn:ogf:network:example:2024:topo:ps2?vlan=200",
    status="ACTIVATED",
    capacity=1000,
):
    return {
        "globalReservationId": "urn:uuid:5fa943ae-32e8-4faa-9080-0bbdc0f405e8",
        "connectionId": connectionId,
        "description": "test reservation",
        "criteria": {
            "version": 1,
            "serviceType": "EVTS.A-GOLE",
            "p2ps": {"capacity": capacity, "sourceSTP": sourceSTP, "destSTP": destSTP},
        },
        "status": status,
        "segments": [],
    }


def _patch_session(db_session):
    """Route amiss.agg.Session (both Session() and Session.begin()) to the test db_session."""
    mock = patch("amiss.agg.Session")
    mock_session_cls = mock.start()
    mock_session_cls.return_value.__enter__ = lambda _: db_session
    mock_session_cls.return_value.__exit__ = lambda *_: None
    mock_session_cls.begin.return_value.__enter__ = lambda _: db_session
    mock_session_cls.begin.return_value.__exit__ = lambda *_: None
    db_session.commit = lambda: None
    return mock


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


class TestSegdictsToSegments:
    def test_builds_segments_with_reservation_id_and_no_id(self):
        from amiss.agg import segdicts_to_segments

        segments = segdicts_to_segments(7, [_segdict(connectionId="a", capacity="500")])

        assert len(segments) == 1
        assert segments[0].id is None
        assert segments[0].reservation_id == 7
        assert segments[0].connectionId == "a"
        assert segments[0].capacity == 500  # coerced from str

    def test_skips_segment_missing_required_key(self):
        from amiss.agg import segdicts_to_segments

        bad = _segdict()
        del bad["sourceSTP"]

        segments = segdicts_to_segments(1, [bad, _segdict(connectionId="ok")])

        assert [s.connectionId for s in segments] == ["ok"]


class TestUpdateSegments:
    def test_skips_when_no_matching_reservation(self, db_session):
        from amiss.agg import update_segments

        mock = _patch_session(db_session)
        try:
            update_segments(str(uuid4()), [_segdict()])
            assert db_session.query(Segment).count() == 0
        finally:
            mock.stop()

    def test_inserts_segments_for_resolved_reservation(self, db_session, reservation_factory):
        from amiss.agg import update_segments

        parent = reservation_factory()
        db_session.add(parent)
        db_session.flush()

        mock = _patch_session(db_session)
        try:
            update_segments(str(parent.connectionId), [_segdict(connectionId="s1"), _segdict(connectionId="s2", order=1)])

            stored = db_session.query(Segment).all()
            assert {s.connectionId for s in stored} == {"s1", "s2"}
            assert all(s.reservation_id == parent.id for s in stored)
        finally:
            mock.stop()

    def test_updates_changed_fields(self, db_session, reservation_factory, segment_factory):
        from amiss.agg import update_segments

        parent = reservation_factory()
        db_session.add(parent)
        db_session.flush()
        db_session.add(segment_factory(connectionId="s1", reservation_id=parent.id, status="ACTIVATED", capacity=1000))
        db_session.flush()

        mock = _patch_session(db_session)
        try:
            update_segments(str(parent.connectionId), [_segdict(connectionId="s1", status="TERMINATED", capacity=2000)])

            stored = db_session.query(Segment).filter(Segment.connectionId == "s1").one()
            assert stored.status == "TERMINATED"
            assert stored.capacity == 2000
        finally:
            mock.stop()

    def test_hard_deletes_vanished_segments_scoped_to_reservation(self, db_session, reservation_factory, segment_factory):
        from amiss.agg import update_segments

        parent = reservation_factory()
        other = reservation_factory()
        db_session.add(parent)
        db_session.add(other)
        db_session.flush()
        db_session.add(segment_factory(connectionId="gone", reservation_id=parent.id))
        db_session.add(segment_factory(connectionId="kept-other", reservation_id=other.id))
        db_session.flush()

        mock = _patch_session(db_session)
        try:
            update_segments(str(parent.connectionId), [_segdict(connectionId="fresh")])

            connection_ids = {s.connectionId for s in db_session.query(Segment).all()}
            # "gone" removed (vanished from parent), "fresh" added, "kept-other" untouched.
            assert connection_ids == {"fresh", "kept-other"}
        finally:
            mock.stop()


class TestTempPullReservationsFromAgg:
    def _seed_stps(self, db_session, stp_factory):
        stp_a = stp_factory(stpId="example:2024:topo:ps1", vlanRange="100-200")
        stp_z = stp_factory(stpId="example:2024:topo:ps2", vlanRange="100-200")
        db_session.add(stp_a)
        db_session.add(stp_z)
        db_session.flush()
        return stp_a, stp_z

    def test_inserts_reservation_resolving_stps_and_vlans(self, db_session, stp_factory):
        from amiss.agg import temp_pull_reservations_from_agg

        stp_a, stp_z = self._seed_stps(db_session, stp_factory)

        mock = _patch_session(db_session)
        try:
            temp_pull_reservations_from_agg([_resdict()])

            reservation = db_session.query(Reservation).one()
            assert reservation.connectionId == UUID("9adfed42-fa58-4d26-bf74-9f5e14ab2281")
            assert reservation.globalReservationId == UUID("5fa943ae-32e8-4faa-9080-0bbdc0f405e8")
            assert reservation.sourceStpId == stp_a.id
            assert reservation.destStpId == stp_z.id
            assert reservation.sourceVlan == 100
            assert reservation.destVlan == 200
            assert reservation.bandwidth == 1000
            assert reservation.state == "ACTIVATED"
        finally:
            mock.stop()

    def test_wipes_existing_reservations_and_segments(self, db_session, reservation_factory, segment_factory):
        from amiss.agg import temp_pull_reservations_from_agg

        old = reservation_factory()
        db_session.add(old)
        db_session.flush()
        db_session.add(segment_factory(connectionId="old-seg", reservation_id=old.id))
        db_session.flush()

        mock = _patch_session(db_session)
        try:
            temp_pull_reservations_from_agg([])  # empty list -> wipe everything, add nothing

            assert db_session.query(Reservation).count() == 0
            assert db_session.query(Segment).count() == 0
        finally:
            mock.stop()

    def test_skips_reservation_with_unknown_stp(self, db_session, stp_factory):
        from amiss.agg import temp_pull_reservations_from_agg

        # Only the A-side STP exists; the dest STP is unknown.
        db_session.add(stp_factory(stpId="example:2024:topo:ps1", vlanRange="100-200"))
        db_session.flush()

        mock = _patch_session(db_session)
        try:
            temp_pull_reservations_from_agg([_resdict()])
            assert db_session.query(Reservation).count() == 0
        finally:
            mock.stop()

    def test_skips_reservation_with_unparseable_vlan(self, db_session, stp_factory):
        from amiss.agg import temp_pull_reservations_from_agg

        self._seed_stps(db_session, stp_factory)

        mock = _patch_session(db_session)
        try:
            # sourceSTP has no ?vlan= -> parse fails -> reservation skipped
            temp_pull_reservations_from_agg([_resdict(sourceSTP="urn:ogf:network:example:2024:topo:ps1")])
            assert db_session.query(Reservation).count() == 0
        finally:
            mock.stop()
