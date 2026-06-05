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
from string import capwords

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

def segdicts_to_segments(parentConnectionIdStr: str, segdicts: list) -> list[Segment]:
    """Parse dict representation of the segments making up the NSI reservation "parentConnectionIdStr"
    and return the lists of Segments."""
    log = logger.bind(topology=parentConnectionIdStr) # ARNOTODO: what does topology param do?

    segments = []

    for segdict in segdicts:
        try:
            order = int(segdict["order"])
            childConnectionId = segdict["connectionId"]
            providerNSA =  segdict["providerNSA"]
            serviceType =  segdict["serviceType"]
            capacity = int(segdict["capacity"])
            sourceStpUrn =  segdict["sourceSTP"]
            destStpUrn =  segdict["destSTP"]
            status = segdict["status"]
        except KeyError as e:
            log.warning("cannot parse reservation JSON", error=f"cannot find {e!s} in reservation JSON")
            continue

        # Find Ids for given source and dest STPs

        segments.append(
            Segment(
                #id=id
                connectionId=childConnectionId,
                reservation_id=parentConnectionIdStr,
                order=order,
                providerNSA=providerNSA,
                serviceType=serviceType,
                capacity=capacity,
                sourceStp=sourceStpUrn,
                destStp=destStpUrn,
                status=status
            )
        )
        log.debug(f"found Segment {childConnectionId}: {segments[-1]}")
    return segments

