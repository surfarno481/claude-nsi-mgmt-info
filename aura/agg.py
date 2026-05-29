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

# ARNOTODO: Convert SDPs to Segment

import base64
import zlib

import structlog
from pydantic import HttpUrl
from sqlalchemy import or_, update

from aura.db import Session
from aura.model import SDP, STP, Segment
from aura.nsi import nsi_util_get_json

logger = structlog.get_logger(__name__)



def segdicts_to_segments(connectionIdStr: str, segdicts: list) -> list[Segment]:
    """Parse dict representation of the segments making up the NSI reservation "connectionIdStr"
    and return the lists of Segments."""
    log = logger.bind(topology=connectionIdStr) # ARNOTODO: what does topology param do?

    try:
        bidirectionalPorts = to_dict("id", topology["BidirectionalPort"])
        relations = to_dict("type", topology["Relation"])
        inboundPorts = to_dict("id", relations[HAS_INBOUND_PORT]["PortGroup"])
        outboundPorts = to_dict("id", relations[HAS_OUTBOUND_PORT]["PortGroup"])
    except KeyError as e:
        log.warning("cannot parse topology", error=f"cannot find {e!s} in topology")
        return []

    stps = []
    for bidirectionalPortId in bidirectionalPorts:
        inboundPort: dict | None = None
        outboundPort: dict | None = None
        for unidirectionalPortId in to_list("id", bidirectionalPorts[bidirectionalPortId]["PortGroup"]):
            if unidirectionalPortId in inboundPorts:
                inboundPort = inboundPorts[unidirectionalPortId]
            elif unidirectionalPortId in outboundPorts:
                outboundPort = outboundPorts[unidirectionalPortId]
            else:
                log.warning(f"unidirectional port {unidirectionalPortId} not found")
        inboundPortId: str | None = None
        outboundPortId: str | None = None
        inboundAliasId: str | None = None
        outboundAliasId: str | None = None
        if inboundPort and outboundPort:
            if inboundPort["LabelGroup"] != outboundPort["LabelGroup"]:
                log.warning(f"LabelGroups on in- and outbound ports of {bidirectionalPortId} do not match")
            # the following breaks when the port has multiple relations, then Relation will be a list instead of a dict
            if "Relation" in inboundPort and inboundPort["Relation"]["type"] == IS_ALIAS:
                inboundPortId = strip_urn(inboundPort["id"])
                inboundAliasId = strip_urn(inboundPort["Relation"]["PortGroup"]["id"])
            if "Relation" in outboundPort and outboundPort["Relation"]["type"] == IS_ALIAS:
                outboundPortId = strip_urn(outboundPort["id"])
                outboundAliasId = strip_urn(outboundPort["Relation"]["PortGroup"]["id"])
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
                active=True,
            )
        )
        log.debug(f"found STP {bidirectionalPortId}: {stps[-1]}")
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


def update_sdps() -> None:
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
    sdps = []
    paired: set[int] = set()
    for a in stps:
        if a.id in paired:
            continue
        for z in stps:
            if z.id in paired or z.id == a.id:
                continue
            if is_sdp(a, z):
                sdps.append((a, z))
                paired.add(a.id)
                paired.add(z.id)
                break
    # process found SDPs
    for stp_a, stp_z in sdps:
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
        existing_sdps = [sorted([sdp.stpAId, sdp.stpZId]) for sdp in session.query(SDP).filter(SDP.active).all()]
        new_sdps = [sorted([sdp[0].id, sdp[1].id]) for sdp in sdps]
        for vanished_sdp in [sdp for sdp in existing_sdps if sorted(sdp) not in new_sdps]:
            stpA = session.query(STP).filter(STP.id == vanished_sdp[0]).one()
            stpZ = session.query(STP).filter(STP.id == vanished_sdp[1]).one()
            logger.info("mark SDP as inactive", stpA=stpA.stpId, stpZ=stpZ.stpId, vlanRange=stpA.vlanRange)
            session.execute(update(SDP).where((SDP.stpAId == stpA.id) & (SDP.stpZId == stpZ.id)).values(active=False))
        session.commit()


