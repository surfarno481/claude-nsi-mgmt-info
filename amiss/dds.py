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

import base64
import zlib

import structlog
from pydantic import HttpUrl
from sqlalchemy import or_, update

from amiss.db import Session
from amiss.model import SDP, STP
from amiss.nsi import nsi_util_get_json, nsi_util_get_xml, nsi_xml_to_dict

logger = structlog.get_logger(__name__)


DISCOVERY_MIME_TYPE = "vnd.ogf.nsi.nsa.v1+xml"
TOPOLOGY_MIME_TYPE = "vnd.ogf.nsi.topology.v2+xml"


def strip_urn(urn: str) -> str:
    return urn.replace("urn:ogf:network:", "")


def to_dict(index: str, collection: list | dict) -> dict:
    if isinstance(collection, dict):
        return {collection[index]: collection}
    if isinstance(collection, list):
        return {element[index]: element for element in collection}
    return {}


def to_list(index: str, collection: dict) -> list:
    return [element[index] for element in collection]


def update_stps(stps: list[STP]) -> None:
    """Update STP table with topology information from DDS."""
    new_stp_ids = [stp.stpId for stp in stps]
    for new_stp in stps:
        log = logger.bind(
            stpId=new_stp.stpId,
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
                existing_stp.vlanRange != new_stp.vlanRange
                or existing_stp.description != new_stp.description  # comment out to enable modify description
                or existing_stp.active != new_stp.active
            ):
                log.info("update existing STP")
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
    """Whether the STP is part of an SDP."""
    return stp.isSdpMember


def unzip(document: dict) -> bytes:
    """Unzip document content to bytes."""
    return zlib.decompress(base64.b64decode(document["content"]), 16 + zlib.MAX_WBITS)


def get_dds_documents(url: HttpUrl) -> dict[str, dict[str, bytes]]:
    """Retrieve all documents from url and return them by type and id.

    Example:
    {'vnd.ogf.nsi.topology.v2+xml': {'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy': b'<ns3:Topology> ...',
                                     'urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf': b'<ns3:Topology> ...',
    'vnd.ogf.nsi.nsa.v1+xml': {'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:nsa:supa': b'<ns3:nsa ...',
                               'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari': b'<ns3:nsa ...',
                               'urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:nsa:supa': b'<ns3:nsa ...'}}

    """
    documents: dict[str, dict[str, bytes]] = {TOPOLOGY_MIME_TYPE: {}, DISCOVERY_MIME_TYPE: {}}

    xml = nsi_util_get_xml(url)  # TODO: catch Exception
    if xml:
        dds = nsi_xml_to_dict(xml)
        if isinstance(dds["documents"]["document"], list):
            for document in dds["documents"]["document"]:
                documents[document["type"]][document["id"]] = unzip(document)
        else:
            documents[document["type"]][document["id"]] = unzip(document := dds["documents"]["document"])

    return documents


def get_dds_proxy_stps(proxy_url: HttpUrl) -> bytes | None:
    """Fetch all service termination points from the DDS proxy.

    Calls the proxy's ``GET /service-termination-points`` endpoint; ``proxy_url`` is the proxy base
    URL, the path is appended to it. Returns the raw JSON body as bytes, or ``None`` if the request
    failed (``nsi_util_get_json`` already logs the reason).
    """
    stps_url = HttpUrl(f"{str(proxy_url).rstrip('/')}/service-termination-points")
    return nsi_util_get_json(stps_url, {})


def dds_proxy_json_to_stps(stp_dicts: list) -> list[STP]:
    """Convert the DDS proxy ``/service-termination-points`` JSON into STP objects.

    The flat DDS-proxy listing carries only id/name/capacity/labelGroup/switchingServiceId, so the
    new STPs default to ``isSdpMember=False`` (SDP membership is set by ``dds_proxy_json_to_sdps``).
    """
    stps = []
    for stp_dict in stp_dicts:
        try:
            stpId = strip_urn(stp_dict["id"])
            vlanRange = stp_dict["labelGroup"]
            description = stp_dict["name"]
        except KeyError as e:
            logger.warning("cannot parse DDS proxy STP", error=f"cannot find {e!s} in STP JSON")
            continue
        stps.append(STP(stpId=stpId, vlanRange=vlanRange, description=description, active=True))
        logger.debug(f"found STP {stpId}: {stps[-1]}")
    return stps


def get_dds_proxy_sdps(proxy_url: HttpUrl) -> bytes | None:
    """Fetch all service demarcation points from the DDS proxy.

    Calls the proxy's ``GET /service-demarcation-points`` endpoint; ``proxy_url`` is the proxy base
    URL, the path is appended to it. Returns the raw JSON body as bytes, or ``None`` if the request
    failed (``nsi_util_get_json`` already logs the reason).
    """
    sdps_url = HttpUrl(f"{str(proxy_url).rstrip('/')}/service-demarcation-points")
    return nsi_util_get_json(sdps_url, {})


def dds_proxy_json_to_sdps(sdp_dicts: list) -> list[SDP]:
    """Persist the SDPs from the DDS proxy ``/service-demarcation-points`` JSON and flag their STPs.

    Each item carries ``stpAId``/``stpZId`` URN strings; resolve each to its STP row, set
    ``isSdpMember=True`` on both, and upsert the SDP (``vlanRange``/``description`` taken from the
    A-side STP). A pair is skipped if either STP is not in the database. Returns the upserted SDPs.
    """
    sdps = []
    with Session.begin() as session:
        for sdp_dict in sdp_dicts:
            try:
                stpAUrn = strip_urn(sdp_dict["stpAId"])
                stpZUrn = strip_urn(sdp_dict["stpZId"])
            except KeyError as e:
                logger.warning("cannot parse DDS proxy SDP", error=f"cannot find {e!s} in SDP JSON")
                continue
            stpA = session.query(STP).filter(STP.stpId == stpAUrn).one_or_none()  # type: ignore[arg-type]
            stpZ = session.query(STP).filter(STP.stpId == stpZUrn).one_or_none()  # type: ignore[arg-type]
            if stpA is None or stpZ is None:
                logger.warning("STP not found for SDP, skipping", stpAId=stpAUrn, stpZId=stpZUrn)
                continue
            stpA.isSdpMember = True
            stpZ.isSdpMember = True
            existing_sdp = (
                session.query(SDP)
                .filter(
                    or_(
                        (SDP.stpAId == stpA.id) & (SDP.stpZId == stpZ.id),  # type: ignore[arg-type]
                        (SDP.stpAId == stpZ.id) & (SDP.stpZId == stpA.id),  # type: ignore[arg-type]
                    )
                )
                .one_or_none()
            )
            description = f"{stpA.description} <-> {stpZ.description}"
            if existing_sdp is None:
                log = logger.bind(stpAId=stpAUrn, stpZId=stpZUrn)
                log.info("add new SDP")
                sdp = SDP(stpAId=stpA.id, stpZId=stpZ.id, vlanRange=stpA.vlanRange, description=description, active=True)
                session.add(sdp)
                sdps.append(sdp)
            else:
                existing_sdp.vlanRange = stpA.vlanRange
                existing_sdp.description = description
                existing_sdp.active = True
                sdps.append(existing_sdp)
    return sdps
