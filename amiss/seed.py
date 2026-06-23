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

Only runs when ``settings.SEED_DUMMY_SEGMENTS_DATA`` is enabled (see ``amiss/__init__.py``); in that
mode the poll jobs are skipped, so nothing wipes these tables. Seeds a small but self-consistent
topology: STPs and SDPs (the ANA inter-domain links) plus the parent Reservations and their Segments.
The STPs/SDPs are what makes the spectrum view work — ``spectrum_detail`` matches each segment's
``sourceStp`` against an SDP's two STPs, so the segments must reference STPs that exist as rows and
the SDPs must sit on the reservation paths.
"""

from uuid import UUID, uuid4

import structlog
from sqlalchemy import or_

from amiss.db import Session
from amiss.fsm import ConnectionStateMachine
from amiss.model import SDP, STP, Reservation, Segment

logger = structlog.get_logger(__name__)

# STP ids are stored stripped of the "urn:ogf:network:" prefix (as dds_proxy_json_to_stps stores them
# and as the segment sourceStp/destStp below reference them).
STP_VLAN_RANGE = "2-4094"

# Dummy STPs: (stpId, description, isSdpMember). isSdpMember is True for STPs that are part of an SDP.
DUMMY_STPS: list[dict] = [
    {"stpId": "internet2.edu:2025:ana:manlan.ps1", "description": "MANLAN ps1 (Internet2 endpoint)", "isSdpMember": False},
    {"stpId": "internet2.edu:2025:ana:manlan.moxy-1", "description": "MANLAN MOXY ANA link (Internet2)", "isSdpMember": True},
    {"stpId": "internet2.edu:2025:ana:manlan.netherlight-1", "description": "MANLAN NetherLight ANA link (Internet2)", "isSdpMember": True},
    {"stpId": "surf.nl:2020:ana:netherlight.moxy-1", "description": "NetherLight MOXY ANA link (SURF)", "isSdpMember": True},
    {"stpId": "surf.nl:2020:ana:netherlight.ps1", "description": "NetherLight ps1 (SURF endpoint)", "isSdpMember": True},
]

# Dummy SDPs: the ANA inter-domain links the reservations cross (stpA/stpZ given as stpIds).
DUMMY_SDPS: list[dict] = [
    {"stpA": "internet2.edu:2025:ana:manlan.moxy-1", "stpZ": "surf.nl:2020:ana:netherlight.moxy-1", "vlanRange": "139,481", "description": "ANA MOXY link: MANLAN <-> NetherLight"},
    {"stpA": "internet2.edu:2025:ana:manlan.netherlight-1", "stpZ": "surf.nl:2020:ana:netherlight.ps1", "vlanRange": "868", "description": "ANA NEA3R link: MANLAN <-> NetherLight"},
]

# All dummy reservations share these endpoint STPs.
RESERVATION_SOURCE_STP = "internet2.edu:2025:ana:manlan.ps1"
RESERVATION_DEST_STP = "surf.nl:2020:ana:netherlight.ps1"

# Parent reservation NSI connectionId (UUID string) -> {description, sdp}. "sdp" is the stpA stpId of
# the SDP this reservation traverses (used to link Reservation <-> SDP).
DUMMY_RESERVATIONS: dict[str, dict] = {
    "663EF9C9-34E7-4401-ADD1-E976072B526B": {"description": "MOXY multi-domain connection (dummy)", "sdp": "internet2.edu:2025:ana:manlan.moxy-1"},
    "193E4258-5AC3-4A99-A6C3-440DF9575E0A": {"description": "MOXY multi-domain connection 2 (dummy)", "sdp": "internet2.edu:2025:ana:manlan.moxy-1"},
    "35A542F5-9657-4EC0-96CE-4DD8A8EB5AB9": {"description": "NEA3R multi-domain connection (dummy)", "sdp": "internet2.edu:2025:ana:manlan.netherlight-1"},
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
    """Idempotently seed the dummy STPs, SDPs, parent Reservations and their Segments (dev/demo only)."""
    # 1. STPs (keyed by stpId).
    with Session.begin() as session:
        for stp_def in DUMMY_STPS:
            existing_stp = session.query(STP).filter(STP.stpId == stp_def["stpId"]).one_or_none()
            if existing_stp is None:
                logger.info("seed dummy STP", stpId=stp_def["stpId"])
                session.add(
                    STP(
                        stpId=stp_def["stpId"],
                        vlanRange=STP_VLAN_RANGE,
                        description=stp_def["description"],
                        isSdpMember=stp_def["isSdpMember"],
                    )
                )

    # 2. SDPs (keyed by the unordered stpA/stpZ pair).
    with Session.begin() as session:
        stp_id_by_stp_id_str = {stp.stpId: stp.id for stp in session.query(STP).all()}
        for sdp_def in DUMMY_SDPS:
            stp_a_id = stp_id_by_stp_id_str.get(sdp_def["stpA"])
            stp_z_id = stp_id_by_stp_id_str.get(sdp_def["stpZ"])
            if stp_a_id is None or stp_z_id is None:  # pragma: no cover - STPs seeded above
                continue
            existing_sdp = (
                session.query(SDP)
                .filter(
                    or_(
                        (SDP.stpAId == stp_a_id) & (SDP.stpZId == stp_z_id),  # type: ignore[arg-type]
                        (SDP.stpAId == stp_z_id) & (SDP.stpZId == stp_a_id),  # type: ignore[arg-type]
                    )
                )
                .one_or_none()
            )
            if existing_sdp is None:
                logger.info("seed dummy SDP", description=sdp_def["description"])
                session.add(
                    SDP(
                        stpAId=stp_a_id,
                        stpZId=stp_z_id,
                        vlanRange=sdp_def["vlanRange"],
                        description=sdp_def["description"],
                    )
                )

    # 3. Reservations (resolve source/dest STP ids and link the SDP they traverse).
    with Session.begin() as session:
        stp_id_by_stp_id_str = {stp.stpId: stp.id for stp in session.query(STP).all()}
        source_stp_id = stp_id_by_stp_id_str[RESERVATION_SOURCE_STP]
        dest_stp_id = stp_id_by_stp_id_str[RESERVATION_DEST_STP]
        for connection_id_str, info in DUMMY_RESERVATIONS.items():
            connection_id = UUID(connection_id_str)
            existing_reservation = (
                session.query(Reservation).filter(Reservation.connectionId == connection_id).one_or_none()  # type: ignore[arg-type]
            )
            if existing_reservation is None:
                linked_sdp = (
                    session.query(SDP).filter(SDP.stpAId == stp_id_by_stp_id_str.get(info["sdp"])).one_or_none()  # type: ignore[arg-type]
                )
                logger.info("seed dummy reservation", connectionId=connection_id_str)
                session.add(
                    Reservation(
                        connectionId=connection_id,
                        globalReservationId=uuid4(),
                        correlationId=uuid4(),
                        description=info["description"],
                        sourceStpId=source_stp_id,
                        destStpId=dest_stp_id,
                        sourceVlan=2,
                        destVlan=2,
                        bandwidth=1,
                        state=ConnectionStateMachine.ConnectionNew.value,
                        sdps=[linked_sdp] if linked_sdp is not None else [],
                    )
                )

    # 4. Segments (keyed by child connectionId, attached to their parent reservation).
    with Session.begin() as session:
        reservation_id_by_connection_id = {
            str(reservation.connectionId).upper(): reservation.id
            for reservation in session.query(Reservation).all()
            if reservation.connectionId is not None
        }
        for segment_def in DUMMY_SEGMENTS:
            reservation_id = reservation_id_by_connection_id.get(segment_def["reservation_connectionId"].upper())
            if reservation_id is None:  # pragma: no cover - parent is seeded just above
                continue
            existing_segment = (
                session.query(Segment).filter(Segment.connectionId == segment_def["connectionId"]).one_or_none()
            )
            if existing_segment is None:
                logger.info("seed dummy segment", connectionId=segment_def["connectionId"])
                session.add(
                    Segment(
                        connectionId=segment_def["connectionId"],
                        reservation_id=reservation_id,
                        order=segment_def["order"],
                        providerNSA=segment_def["providerNSA"],
                        serviceType=segment_def["serviceType"],
                        capacity=segment_def["capacity"],
                        sourceStp=segment_def["sourceStp"],
                        destStp=segment_def["destStp"],
                        status=segment_def["status"],
                    )
                )
