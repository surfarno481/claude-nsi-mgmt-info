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

from amiss.model import Reservation, Segment


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


class TestSeed:
    def test_seeds_dummy_reservations_and_segments(self, db_session):
        from amiss.seed import DUMMY_RESERVATIONS, DUMMY_SEGMENTS, seed

        mock = _patch_session(db_session)
        try:
            seed()
        finally:
            mock.stop()

        assert db_session.query(Reservation).count() == len(DUMMY_RESERVATIONS)
        assert db_session.query(Segment).count() == len(DUMMY_SEGMENTS)
        # Every seeded segment resolved to a real parent reservation id.
        reservation_ids = {r.id for r in db_session.query(Reservation).all()}
        assert all(s.reservation_id in reservation_ids for s in db_session.query(Segment).all())

    def test_is_idempotent(self, db_session):
        from amiss.seed import DUMMY_RESERVATIONS, DUMMY_SEGMENTS, seed

        mock = _patch_session(db_session)
        try:
            seed()
            seed()
        finally:
            mock.stop()

        assert db_session.query(Reservation).count() == len(DUMMY_RESERVATIONS)
        assert db_session.query(Segment).count() == len(DUMMY_SEGMENTS)
