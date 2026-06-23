#  Copyright 2025 SURF.
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Idempotent seeding of dummy dev/demo data.

Only runs when ``settings.SEED_DUMMY_SEGMENTS_DATA`` is enabled (see ``amiss/__init__.py``).
Because ``Segment.reservation_id`` is a foreign key to ``Reservation.id``, the dummy segments need
parent reservations to exist; ``seed()`` therefore inserts both. These reservations exist purely so
the FK resolves — the spectrum view matches segments by ``sourceStp``, not by the reservation FK.
"""

from uuid import UUID, uuid4

import structlog

from amiss.db import Session
from amiss.fsm import ConnectionStateMachine
from amiss.model import Reservation, Segment

logger = structlog.get_logger(__name__)

# Parent reservation NSI connectionId (UUID string) -> description.
DUMMY_RESERVATIONS: dict[str, str] = {
    "663EF9C9-34E7-4401-ADD1-E976072B526B": "MOXY multi-domain connection (dummy)",
    "193E4258-5AC3-4A99-A6C3-440DF9575E0A": "MOXY multi-domain connection 2 (dummy)",
    "35A542F5-9657-4EC0-96CE-4DD8A8EB5AB9": "NEA3R multi-domain connection (dummy)",
}

# Dummy child segments. ``reservation_connectionId`` references a key in DUMMY_RESERVATIONS above.
DUMMY_SEGMENTS: list[dict] = [
    {"connectionId": "2B20AC13-9246-4060-B2BB-F08D1B08C830", "reservation_connectionId": "663EF9C9-34E7-4401-ADD1-E976072B526B", "order": 0, "providerNSA": "SupaDuppa", "serviceType": "EVTS.A-GOLE", "capacity": 32768, "sourceStp": "internet2.edu:2025:ana:manlan.ps1", "destStp": "internet2.edu:2025:ana:manlan.moxy-1?vlan=481", "status": "ACTIVE"},
    {"connectionId": "2B20AC13-9246-4060-B2BB-F08D1B08C831", "reservation_connectionId": "663EF9C9-34E7-4401-ADD1-E976072B526B", "order": 1, "providerNSA": "SupaDuppa", "serviceType": "EVTS.A-GOLE", "capacity": 32768, "sourceStp": "internet2.edu:2025:ana:manlan.moxy-1?vlan=481", "destStp": "surf.nl:2020:ana:netherlight.moxy-1?vlan=481", "status": "ACTIVE"},
    {"connectionId": "2B20AC13-9246-4060-B2BB-F08D1B08C832", "reservation_connectionId": "663EF9C9-34E7-4401-ADD1-E976072B526B", "order": 2, "providerNSA": "SupaDuppa", "serviceType": "EVTS.A-GOLE", "capacity": 32768, "sourceStp": "surf.nl:2020:ana:netherlight.moxy-1?vlan=481", "destStp": "surf.nl:2020:ana:netherlight.ps1", "status": "ACTIVE"},
    {"connectionId": "2B20AC13-9246-4060-B2BB-F08D1B08C833", "reservation_connectionId": "193E4258-5AC3-4A99-A6C3-440DF9575E0A", "order": 0, "providerNSA": "SupaDuppa", "serviceType": "EVTS.A-GOLE", "capacity": 32768, "sourceStp": "internet2.edu:2025:ana:manlan.ps1", "destStp": "internet2.edu:2025:ana:manlan.moxy-1?vlan=139", "status": "ACTIVE"},
    {"connectionId": "2B20AC13-9246-4060-B2BB-F08D1B08C834", "reservation_connectionId": "193E4258-5AC3-4A99-A6C3-440DF9575E0A", "order": 1, "providerNSA": "SupaDuppa", "serviceType": "EVTS.A-GOLE", "capacity": 32768, "sourceStp": "internet2.edu:2025:ana:manlan.moxy-1?vlan=139", "destStp": "surf.nl:2020:ana:netherlight.moxy-1?vlan=139", "status": "ACTIVE"},
    {"connectionId": "2B20AC13-9246-4060-B2BB-F08D1B08C836", "reservation_connectionId": "193E4258-5AC3-4A99-A6C3-440DF9575E0A", "order": 2, "providerNSA": "SupaDuppa", "serviceType": "EVTS.A-GOLE", "capacity": 32768, "sourceStp": "surf.nl:2020:ana:netherlight.moxy-1?vlan=139", "destStp": "surf.nl:2020:ana:netherlight.ps1", "status": "ACTIVE"},
    {"connectionId": "BA676DA4-F232-45C8-9CF4-079D9D8BE560", "reservation_connectionId": "35A542F5-9657-4EC0-96CE-4DD8A8EB5AB9", "order": 0, "providerNSA": "SupaDuppa", "serviceType": "EVTS.A-GOLE", "capacity": 32768, "sourceStp": "internet2.edu:2025:ana:manlan.ps1", "destStp": "internet2.edu:2025:ana:manlan.netherlight-1?vlan=868", "status": "ACTIVE"},
    {"connectionId": "BA676DA4-F232-45C8-9CF4-079D9D8BE561", "reservation_connectionId": "35A542F5-9657-4EC0-96CE-4DD8A8EB5AB9", "order": 1, "providerNSA": "SupaDuppa", "serviceType": "EVTS.A-GOLE", "capacity": 32768, "sourceStp": "internet2.edu:2025:ana:manlan.netherlight-1?vlan=868", "destStp": "surf.nl:2020:ana:netherlight.ps1", "status": "ACTIVE"},
]


def seed() -> None:
    """Idempotently seed the dummy parent Reservations and their Segments (dev/demo only)."""
    with Session.begin() as session:
        for connection_id_str, description in DUMMY_RESERVATIONS.items():
            connection_id = UUID(connection_id_str)
            existing = (
                session.query(Reservation).filter(Reservation.connectionId == connection_id).one_or_none()  # type: ignore[arg-type]
            )
            if existing is None:
                logger.info("seed dummy reservation", connectionId=connection_id_str)
                session.add(
                    Reservation(
                        connectionId=connection_id,
                        globalReservationId=uuid4(),
                        correlationId=uuid4(),
                        description=description,
                        sourceStpId=1,
                        destStpId=2,
                        sourceVlan=2,
                        destVlan=2,
                        bandwidth=1,
                        state=ConnectionStateMachine.ConnectionNew.value,
                    )
                )

    with Session.begin() as session:
        reservation_id_by_connection_id = {
            str(reservation.connectionId).upper(): reservation.id
            for reservation in session.query(Reservation).all()
            if reservation.connectionId is not None
        }
        for segment in DUMMY_SEGMENTS:
            reservation_id = reservation_id_by_connection_id.get(segment["reservation_connectionId"].upper())
            if reservation_id is None:  # pragma: no cover - parent is seeded just above
                continue
            existing_segment = (
                session.query(Segment).filter(Segment.connectionId == segment["connectionId"]).one_or_none()
            )
            if existing_segment is None:
                logger.info("seed dummy segment", connectionId=segment["connectionId"])
                session.add(
                    Segment(
                        connectionId=segment["connectionId"],
                        reservation_id=reservation_id,
                        order=segment["order"],
                        providerNSA=segment["providerNSA"],
                        serviceType=segment["serviceType"],
                        capacity=segment["capacity"],
                        sourceStp=segment["sourceStp"],
                        destStp=segment["destStp"],
                        status=segment["status"],
                    )
                )
