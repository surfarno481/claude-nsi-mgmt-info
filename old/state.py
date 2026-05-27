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

import threading

from aura.model import Endpoint, NetworkLink, Reservation
from aura.settings import settings

#
# State
#
ONLINE = False
global_provider_nsa_id = ""

# 1 dummy reservation
DUMMY_CONNECTION_ID_STR = "d940e5b1-ed22-4c1a-ae09-10f20e4bd267"  # without urn:uuid: prefix.
DUMMY_CORRELATION_ID_STR = "a3eb6740-7227-473b-af6f-6705d489407c"  # without urn:uuid: prefix.

# define some endpoints
global_endpoints = [
    Endpoint(id=1, name="moxy-cie-01_eth0", svlanid=190, evlanid=190, domain="CANARIE"),
    Endpoint(id=2, name="esnet-csc-01_eth1", svlanid=293, evlanid=293, domain="ESnet"),
    Endpoint(id=3, name="paris-nok-06_eth2", svlanid=391, evlanid=391, domain="Geant"),
    Endpoint(id=4, name="manlan-ari-05_eth3", svlanid=492, evlanid=492, domain="Internet2"),
    Endpoint(id=5, name="seoul-jnx-06_eth4", svlanid=591, evlanid=591, domain="KREONET"),
    Endpoint(id=6, name="nea3r-nok-01_eth5", svlanid=692, evlanid=692, domain="NEA3R"),
    Endpoint(id=7, name="noma-nok-06_eth7", svlanid=791, evlanid=791, domain="NORDUnet"),
    Endpoint(id=8, name="sinet-nok-06_eth8", svlanid=891, evlanid=891, domain="Sinet"),
    Endpoint(id=9, name="nlight-jnx-06_eth9", svlanid=991, evlanid=991, domain="SURF"),
]

# define some ANA links
global_links = [
    NetworkLink(
        id=1,
        name="MOXY EXA Atlantic North 100G",
        linkid=31,
        svlanid=190,
        evlanid=190,
        domain=settings.DEFAULT_LINK_DOMAIN,
    ),
    NetworkLink(
        id=2,
        name="Tata TGN-Atlantic South 100G",
        linkid=32,
        svlanid=190,
        evlanid=190,
        domain=settings.DEFAULT_LINK_DOMAIN,
    ),
    NetworkLink(
        id=3,
        name="AquaComms AEC-1 South 100G",
        linkid=33,
        svlanid=190,
        evlanid=190,
        domain=settings.DEFAULT_LINK_DOMAIN,
    ),
    NetworkLink(
        id=3,
        name="EXA Express 100G",
        linkid=34,
        svlanid=190,
        evlanid=190,
        domain=settings.DEFAULT_LINK_DOMAIN,
    ),
    NetworkLink(
        id=5,
        name="Amitie 400G",
        linkid=35,
        svlanid=190,
        evlanid=190,
        domain=settings.DEFAULT_LINK_DOMAIN,
    ),
]

# GUI polling for Orchestrator async reply using GET
pollcount = 481

#
# Producer/Consumer type interaction between GUI and Orchestrator async callbacks
# TODO: won't work with multi-process fastAPI application
#
global_orch_async_replies_lock = threading.Lock()
global_orch_async_replies_dict = {}  # indexed on CorrelationId
global_soap_provider_url = ""

#
# Reservations
#
global_reservations = [
    Reservation(
        id=1,
        connectionId=DUMMY_CONNECTION_ID_STR,
        description="Dummy reservation",
        startTime="2024-11-07T15:53:32+00:00",
        endTime="2024-11-07T15:53:36+00:00",
        sourceSTP="asd001b-jnx-06_eth0",
        destSTP="mon001a-nok-01_eth1",
        requesterNSA="urn:ogf:network:anaeng.global:2024:nsa:nsi-aura",
        reservationState="ReserveHeld",
        lifecycleState="Created",
        dataPlaneStatus="true",
    ),
]

# SOAP templates now loaded in nsi_comm.py
