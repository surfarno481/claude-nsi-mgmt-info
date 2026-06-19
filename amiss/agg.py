# Copyright 2024-2025 SURF.
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

from uuid import UUID, uuid4

import structlog
from pydantic import HttpUrl
from sqlalchemy import delete

from amiss.db import Session
from amiss.dds import strip_urn
from amiss.model import STP, Reservation, ReservationSDPLink, Segment
from amiss.nsi import nsi_util_get_json

logger = structlog.get_logger(__name__)

"""
{
  "globalReservationId": "urn:uuid:5fa943ae-32e8-4faa-9080-0bbdc0f405e8",
  "connectionId": "9adfed42-fa58-4d26-bf74-9f5e14ab2281",
  "description": "My first multi domain connection",
  "criteria": {
    "version": 1,
    "serviceType": "http://services.ogf.org/nsi/2013/12/descriptions/EVTS.A-GOLE",
    "p2ps": {
      "capacity": 1000,
      "sourceSTP": "urn:ogf:network:x.domain.toplevel:2020:topology:ps1?vlan=1790",
      "destSTP": "urn:ogf:network:y.domain.toplevel:2025:topology:ps2?vlan=1790"
    }
  },
  "status": "ACTIVATED",
  "lastError": null,
  "segments": [
    {
      "order": 0,
      "connectionId": "child-seg-0",
      "providerNSA": "urn:ogf:network:west.example.net:2025:nsa:supa",
      "serviceType": "http://services.ogf.org/nsi/2013/12/descriptions/EVTS.A-GOLE",
      "capacity": 1000,
      "sourceSTP": "urn:ogf:network:west.example.net:2025:port-a?vlan=100",
      "destSTP": "urn:ogf:network:west.example.net:2025:port-b?vlan=200",
      "status": "ACTIVATED"
    }
  ]
}
"""

def get_aggregator_reservations(proxy_url: HttpUrl) -> bytes | None:
    """Fetch all reservations with full segment detail from the aggregator proxy.

    Calls the aggregator proxy's ``GET /reservations`` endpoint with ``detail=full`` so the
    returned reservations include their path ``segments``. ``proxy_url`` is the proxy base URL
    (e.g. ``settings.NSI_AGG_PROXY_URL``); the ``/reservations`` path is appended to it.

    Returns the raw JSON response body as bytes, or ``None`` if the request failed
    (the underlying ``nsi_util_get_json`` already logs the reason).
    """
    reservations_url = HttpUrl(f"{str(proxy_url).rstrip('/')}/reservations")
    queryparams = {"detail": "full"}
    return nsi_util_get_json(reservations_url, queryparams)


def segdicts_to_segments(reservation_id: int, segdicts: list) -> list[Segment]:
    """Parse the aggregator-proxy ``segdicts`` of a parent reservation into ``Segment`` objects.

    ``reservation_id`` is the parent ``Reservation.id`` these segments belong to; it is stored on
    each Segment as the foreign key. The returned Segments are transient (no ``id`` assigned yet).
    """
    log = logger.bind(reservation_id=reservation_id)

    segments = []

    for segdict in segdicts:
        try:
            order = int(segdict["order"])
            childConnectionId = segdict["connectionId"]
            providerNSA = segdict["providerNSA"]
            serviceType = segdict["serviceType"]
            capacity = int(segdict["capacity"])
            sourceStpUrn = segdict["sourceSTP"]
            destStpUrn = segdict["destSTP"]
            status = segdict["status"]
        except KeyError as e:
            log.warning("cannot parse reservation JSON", error=f"cannot find {e!s} in reservation JSON")
            continue

        segments.append(
            Segment(
                connectionId=childConnectionId,
                reservation_id=reservation_id,
                order=order,
                providerNSA=providerNSA,
                serviceType=serviceType,
                capacity=capacity,
                sourceStp=sourceStpUrn,
                destStp=destStpUrn,
                status=status,
            )
        )
        log.debug(f"found Segment {childConnectionId}: {segments[-1]}")
    return segments


def update_segments(parentConnectionId: str, segdicts: list) -> None:
    """Persist the segments of the parent reservation identified by ``parentConnectionId``.

    Resolves ``parentConnectionId`` (an NSI connection id) to its ``Reservation``, then upserts the
    parsed segments keyed by their child ``connectionId`` and hard-deletes any previously-stored
    segments of that reservation that are no longer reported. Segments whose parent reservation is
    not (yet) in the database are skipped with a warning.
    """
    log = logger.bind(parentConnectionId=parentConnectionId)
    with Session.begin() as session:
        reservation = (
            session.query(Reservation).filter(Reservation.connectionId == UUID(parentConnectionId)).one_or_none()  # type: ignore[arg-type]
        )
        if reservation is None:
            log.warning("no reservation for connectionId, skipping segments")
            return
        reservation_id = reservation.id
        if reservation_id is None:  # pragma: no cover - a persisted reservation always has an id
            return

        new_segments = segdicts_to_segments(reservation_id, segdicts)
        new_connection_ids = [segment.connectionId for segment in new_segments]

        for new_segment in new_segments:
            existing = (
                session.query(Segment)
                .filter(
                    Segment.reservation_id == reservation_id,  # type: ignore[arg-type]
                    Segment.connectionId == new_segment.connectionId,  # type: ignore[arg-type]
                )
                .one_or_none()
            )
            if existing is None:
                log.info("add new Segment", connectionId=new_segment.connectionId)
                session.add(new_segment)
            elif (
                existing.reservation_id != new_segment.reservation_id
                or existing.order != new_segment.order
                or existing.providerNSA != new_segment.providerNSA
                or existing.serviceType != new_segment.serviceType
                or existing.capacity != new_segment.capacity
                or existing.sourceStp != new_segment.sourceStp
                or existing.destStp != new_segment.destStp
                or existing.status != new_segment.status
            ):
                log.info("update existing Segment", connectionId=new_segment.connectionId)
                existing.reservation_id = new_segment.reservation_id
                existing.order = new_segment.order
                existing.providerNSA = new_segment.providerNSA
                existing.serviceType = new_segment.serviceType
                existing.capacity = new_segment.capacity
                existing.sourceStp = new_segment.sourceStp
                existing.destStp = new_segment.destStp
                existing.status = new_segment.status
            else:
                log.debug("Segment did not change", connectionId=new_segment.connectionId)

        # Hard-delete segments of this reservation that are no longer reported.
        session.execute(
            delete(Segment).where(
                Segment.reservation_id == reservation_id,  # type: ignore[arg-type]
                Segment.connectionId.not_in(new_connection_ids),  # type: ignore[attr-defined]
            )
        )


def _parse_stp_urn(urn: str) -> tuple[str, int]:
    """Split an aggregator STP URN like ``urn:ogf:network:...:ps1?vlan=1790`` into (stpId, vlan).

    Raises ``ValueError``/``IndexError`` when the ``?vlan=`` query is missing or not a single int.
    """
    base, _, query = urn.partition("?")
    stpId = strip_urn(base)
    vlan = int(query.split("=", 1)[1])
    return stpId, vlan


def temp_pull_reservations_from_agg(reservations: list) -> None:
    """TEMP: replace all reservations in the DB with those reported by the aggregator proxy.

    This is a temporary solution. Reservations should instead be pulled from the WFO (workflow
    orchestrator, ``settings.NSI_AMISS_WFO_URL``), which is the Source of Truth for reservations;
    the aggregator proxy is only used here as a stopgap source.

    Wipes Segment, ReservationSDPLink and Reservation, then inserts a Reservation per aggregator
    reservation. Source/dest STP URNs are resolved to STP rows for the int FKs and the VLAN comes
    from the URN's ?vlan=; a reservation is skipped (with a warning) if either STP is unknown or the
    data can't be parsed. Segments are repopulated afterwards by update_segments.
    """
    with Session.begin() as session:
        session.execute(delete(Segment))
        session.execute(delete(ReservationSDPLink))
        session.execute(delete(Reservation))
        for resdict in reservations:
            log = logger.bind(connectionId=resdict.get("connectionId"))
            try:
                connection_id = UUID(resdict["connectionId"])
                global_reservation_id = UUID(resdict["globalReservationId"].replace("urn:uuid:", ""))
                description = resdict["description"]
                p2ps = resdict["criteria"]["p2ps"]
                bandwidth = int(p2ps["capacity"])
                source_stp_id, source_vlan = _parse_stp_urn(p2ps["sourceSTP"])
                dest_stp_id, dest_vlan = _parse_stp_urn(p2ps["destSTP"])
                status = resdict["status"]
            except (KeyError, ValueError, IndexError, AttributeError) as e:
                log.warning("cannot parse aggregator reservation, skipping", error=str(e))
                continue
            source_stp = session.query(STP).filter(STP.stpId == source_stp_id).one_or_none()  # type: ignore[arg-type]
            dest_stp = session.query(STP).filter(STP.stpId == dest_stp_id).one_or_none()  # type: ignore[arg-type]
            if source_stp is None or dest_stp is None:
                log.warning("STP not found, skipping reservation", sourceStp=source_stp_id, destStp=dest_stp_id)
                continue
            session.add(
                Reservation(
                    connectionId=connection_id,
                    globalReservationId=global_reservation_id,
                    correlationId=uuid4(),
                    description=description,
                    sourceStpId=source_stp.id,
                    destStpId=dest_stp.id,
                    sourceVlan=source_vlan,
                    destVlan=dest_vlan,
                    bandwidth=bandwidth,
                    state=status,
                )
            )
            log.info("added reservation from aggregator")

