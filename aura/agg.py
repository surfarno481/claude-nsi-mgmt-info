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

# ARNOTODO: Convert code for SDPs to Segment

import base64
import zlib

import structlog
from pydantic import HttpUrl
from sqlalchemy import or_, update

from aura.db import Session
from aura.model import SDP, STP, Segment
from aura.nsi import nsi_util_get_json

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

def segdicts_to_segments(connectionIdStr: str, segdicts: list) -> list[Segment]:
    """Parse dict representation of the segments making up the NSI reservation "connectionIdStr"
    and return the lists of Segments."""
    log = logger.bind(topology=connectionIdStr) # ARNOTODO: what does topology param do?

    segments = []

    for segdict in segdicts:
        try:
            order = int(segdict["order"]
            childConnectionId = segdict["connectionId"]
            providerNSA =  segdict["providerNSA"]
            serviceType =  segdict["serviceType"]
            capacity = int(segdict["capacity"]
            sourceStpUrn =  segdict["sourceSTP"]
            destStpUrn =  segdict["destSTP"]
            status = segdict["status"]
        except KeyError as e:
            log.warning("cannot parse reservation JSON", error=f"cannot find {e!s} in reservation JSON")
            continue

        # Find Ids for given source and dest STPs

        stps.append(
            STP(
                stpId=strip_urn(bidirectionalPortId),
                inboundPort=inboundPortId,
                outboundPort=outboundPortId,
                inboundAlias=inboundAliasId,
                outboundAlias=outboundAliasId,
                vlanRange=inboundPort["LabelGroup"] if inboundPort else "",
                description=(
                    bidirectionalPorts[bidirectionalPortId]["name"]
                    if bidirectionalPorts[bidirectionalPortId]["name"]
                    else ""
                ),
                status=status,
            )
        )
        log.debug(f"found Segment {bidirectionalPortId}: {stps[-1]}")



    return stps


def update_stps(stps: list[STP]) -> None:
    """Update STP table with topology information from DDS."""
    new_stp_ids = [stp.stpId for stp in stps]
    for new_stp in stps:
        log = logger.bind(
            stpId=new_stp.stpId,
            inboundPort=new_stp.inboundPort,
            outboundPort=new_stp.outboundPort,
            inboundAlias=new_stp.inboundAlias,
            outboundAlias=new_stp.outboundAlias,
            vlanRange=new_stp.vlanRange,
            description=new_stp.description,
            active=new_stp.active,
        )
        with Session.begin() as session:
            existing_stp = session.query(STP).filter(STP.stpId == new_stp.stpId).one_or_none()  # type: ignore[arg-type]
            if existing_stp is None:
                log.info("add new STP")
                session.add(new_stp)
            elif (
                existing_stp.inboundPort != new_stp.inboundPort
                or existing_stp.outboundPort != new_stp.outboundPort
                or existing_stp.inboundAlias != new_stp.inboundAlias
                or existing_stp.outboundAlias != new_stp.outboundAlias
                or existing_stp.vlanRange != new_stp.vlanRange
                or existing_stp.description != new_stp.description  # comment out to enable modify description
                or existing_stp.active != new_stp.active
            ):
                log.info("update existing STP")
                existing_stp.inboundPort = new_stp.inboundPort
                existing_stp.outboundPort = new_stp.outboundPort
                existing_stp.inboundAlias = new_stp.inboundAlias
                existing_stp.outboundAlias = new_stp.outboundAlias
                existing_stp.vlanRange = new_stp.vlanRange
                existing_stp.description = new_stp.description  # comment out to enable modify description
                existing_stp.active = new_stp.active
            else:
                log.debug("STP did not change")
    with Session.begin() as session:
        existing_stp_ids = [row[0] for row in session.query(STP.stpId).filter(STP.active).all()]
        for vanished_stp_id in [stpId for stpId in existing_stp_ids if stpId not in new_stp_ids]:
            logger.info("mark STP as inactive", stpId=vanished_stp_id)
            session.execute(update(STP).where(STP.stpId == vanished_stp_id).values(active=False))
        session.commit()


def has_alias(stp: STP) -> bool:
    return stp.inboundAlias is not None and stp.outboundAlias is not None


def update_segments() -> None:
    """Update SDP table."""

    def is_sdp(a: STP, z: STP) -> bool:
        return (
            has_alias(a)
            and has_alias(z)
            and a.inboundAlias == z.outboundPort
            and a.outboundAlias == z.inboundPort
            and z.inboundAlias == a.outboundPort
            and z.outboundAlias == a.inboundPort
        )

    with Session() as session:
        stps = session.query(STP).filter(STP.active == True).all()
    # find connected STPs
    segments = []
    paired: set[int] = set()
    for a in stps:
        if a.id in paired:
            continue
        for z in stps:
            if z.id in paired or z.id == a.id:
                continue
            if is_sdp(a, z):
                segments.append((a, z))
                paired.add(a.id)
                paired.add(z.id)
                break
    # process found SDPs
    for stp_a, stp_z in segments:
        description = f"{stp_a.description} <-> {stp_z.description}"
        log = logger.bind(
            stpAId=stp_a.stpId,
            stpZId=stp_z.stpId,
            vlanRange=stp_a.vlanRange,  # TODO: should store a and z overlapping range only
            description=description,
            active=True,
        )
        with Session.begin() as session:
            existing_sdp = (
                session.query(SDP)
                .filter(
                    or_(
                        (SDP.stpAId == stp_a.id) & (SDP.stpZId == stp_z.id),
                        (SDP.stpAId == stp_z.id) & (SDP.stpZId == stp_a.id),
                    )
                )
                .one_or_none()
            )  # type: ignore[arg-type]
            if existing_sdp is None:
                log.info("add new SDP")
                session.add(
                    SDP(
                        stpAId=stp_a.id,
                        stpZId=stp_z.id,
                        vlanRange=stp_a.vlanRange,  # TODO: should store a and z overlapping range only
                        description=description,
                    )
                )
            elif (
                existing_sdp.vlanRange != stp_a.vlanRange
                or existing_sdp.description != description  # comment out to enable modify description
                or not existing_sdp.active
            ):
                log.info("update existing SDP")
                existing_sdp.vlanRange = stp_a.vlanRange  # TODO: should store a and z overlapping range only
                existing_sdp.description = description  # comment out to enable modify description
                existing_sdp.active = True
            else:
                log.debug("SDP did not change")
    with Session.begin() as session:
        existing_segments = [sorted([sdp.stpAId, sdp.stpZId]) for sdp in session.query(SDP).filter(SDP.active).all()]
        new_segments = [sorted([sdp[0].id, sdp[1].id]) for sdp in segments]
        for vanished_sdp in [sdp for sdp in existing_segments if sorted(sdp) not in new_segments]:
            stpA = session.query(STP).filter(STP.id == vanished_sdp[0]).one()
            stpZ = session.query(STP).filter(STP.id == vanished_sdp[1]).one()
            logger.info("mark SDP as inactive", stpA=stpA.stpId, stpZ=stpZ.stpId, vlanRange=stpA.vlanRange)
            session.execute(update(SDP).where((SDP.stpAId == stpA.id) & (SDP.stpZId == stpZ.id)).values(active=False))
        session.commit()


