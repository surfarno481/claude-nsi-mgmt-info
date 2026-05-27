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

import copy
import secrets

from fastapi import HTTPException, Request
from fastui import AnyComponent
from fastui import components as c
from fastui.components.display import DisplayLookup
from fastui.events import BackEvent, GoToEvent

import aura.state
from aura.model import Discovery, Endpoint, NetworkLink, Span
from aura.nsi_comm import *
from aura.settings import settings

logger = structlog.get_logger(__name__)

#
# NSI-AuRA = NSI ANA ultimate Requester Agent
# ===========================================
# @author: Arno Bakker
#
# CSS can be controlled via class_name attribute and
# https://getbootstrap.com/docs/4.5/utilities/colors/ definitions
#
# TODO:
# - Concurrency control on the Model data: endpoints, links, reservations
#   * This includes changing URLs to use absolute endpoint and link identifiers, so really RESTful
# - Export HTTP exceptions to fastUI level, so they can be signalled to user.
# - Security for NOC access, see /login /logout already below.
# - Global Reservation Id in Reserve message is apparently unique to uPA, Orchestrator/Safnari barfs.
# - footer is separate construct?
#

# pydantic suckx
c.Link.model_rebuild()

#
# Security: Session cookies as per
#
#     https://gist.github.com/rochacbruno/3b8dbb79b2b6c54486c396773fdde532
#
#

# This must be randomly generated
RANDON_SESSION_ID = "see below"

# This must be a lookup on user database
USER_CORRECT = ("arno", "tshirtdeal")

# This must be Redis, Memcached, SQLite, KV, etc...
SESSION_DB = {}


def create_and_record_sessionid(username):
    # Arno
    sessionid_b64str = secrets.token_urlsafe(16)
    SESSION_DB[sessionid_b64str] = username
    return sessionid_b64str


def get_auth_user(request: Request):
    """Verify that user has a valid session"""
    session_id = request.cookies.get("Authorization")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authorized to use AuRA, please login")
    if session_id not in SESSION_DB:
        raise HTTPException(status_code=403, detail="Please login to use AuRA")
    return True


def discoverydict2model(disccount, disc_metadata_dict):
    log = logger.bind()

    disc_dict = disc_metadata_dict["metadata"]
    log.debug("DISC2DATAMODEL:", disc_dict=disc_dict)

    agentid = disc_dict["id"]
    version = disc_dict["version"]
    expires = disc_dict["expires"]
    return Discovery(id=disccount, agentid=agentid, version=version, expires=expires)


#
# SOAP templating
#


def nsi_load_dds_documents():
    """Contact hard-coded DDS for ANA to discovery
    a. who is the Orchestrator
    b. discovery and topology information for all connected NSI uPAs

    Retrieves DDS info, and loads into data Models
    Also sets
    - global_provider_nsa_id
    - global_soap_provider_url
    returns dds_documents_dict for displaying summaries to the user
    """
    log = logger.bind()  # TODO: maek log function specific

    dds_documents_dict = nsi_get_dds_documents(str(settings.NSI_DDS_URL))

    # DDS knows all, so also who is our Orchestrator/Safnari
    orchestrator_dict = dds_documents_dict["local"]
    aura.state.global_provider_nsa_id = orchestrator_dict["metadata"]["id"]
    aura.state.global_soap_provider_url = orchestrator_dict["services"][SOAP_PROVIDER_MIME_TYPE]

    log.debug("nsi_load_dds_documents: Found Aggregator ID", global_provider_nsa_id=aura.state.global_provider_nsa_id)
    log.debug(
        "nsi_load_dds_documents: Found Aggregator SOAP", global_soap_provider_url=aura.state.global_soap_provider_url
    )

    worldwide_stps = {}
    worldwide_sdp_list = []
    documents = dds_documents_dict["documents"]
    for upa_id in documents.keys():
        log.debug("nsi_load_dds_documents: Found uPA", upa_id=upa_id)

        # Load topologies, compose list of STPs (aka Endpoints) and SDPs (aka Links)
        document = documents[upa_id]
        topo_dict = document["topology"]
        stps = topo_dict["stps"]
        sdps = topo_dict["sdps"]

        log.debug("nsi_load_dds_documents: Adding STPs", len=len(stps), stps=stps)
        log.debug("nsi_load_dds_documents: Adding SDPs", len=len(sdps), sdps=stps)

        worldwide_stps.update(stps)

        # TODO: merge, so check for duplicates
        worldwide_sdp_list += sdps  # append

    # Load new data into Datamodel
    nsi_reload_topology_into_endpoints_model(worldwide_stps)
    nsi_reload_topology_into_links_model(worldwide_sdp_list)

    # update ServiceTerminationPoint's in database
    # update_service_termination_points_from_dds(worldwide_stps)

    aura.state.ONLINE = True
    return dds_documents_dict, worldwide_stps, worldwide_sdp_list


def nsi_reload_topology_into_endpoints_model(stps):
    """Updates global DataModel endpoints to contain the given list of STPs
    Returns nothing
    """
    aura.state.global_endpoints = stps2endpoints(stps)


def parse_vlan_range(vlanstr):
    """Takes a VLAN spec with either a single VLAN or range and converts it to
    (start VLAN id,end VLAN id)
    """
    idx = vlanstr.find("-")
    if idx == -1:
        # Qualified STP, just one vlan ID
        svlanid = int(vlanstr)
        evlanid = svlanid
    else:
        vlanstrings = vlanstr.split("-")
        svlanid = int(vlanstrings[0])
        evlanid = int(vlanstrings[1])
    return (svlanid, evlanid)


def stpid2domain(stpid):
    """Abbreviates STP id to a simple domain name for display purposes"""
    urn = stpid
    nopref = urn[len(settings.UPA_URN_PREFIX) :]
    idx = nopref.find(":")
    domain = nopref[:idx]
    return domain


def add_endpoint(id, stpid, svlanid, evlanid, domain, local_endpoints):
    endpoint = Endpoint(id=id, name=stpid, svlanid=svlanid, evlanid=evlanid, domain=domain)
    # Put in list
    local_endpoints.append(endpoint)


def stps2endpoints(stps):
    """Take downloaded STPs and put into a DataModel Endpoints list
    Returns list
    """
    log = logger.bind()

    local_endpoints = []
    bidiports = stps

    log.debug("nsi_reload_topology_into_endpoints_model: Loading STPs", bidiports=bidiports)
    if bidiports is None:
        return local_endpoints

    endpointcount = 1

    for stpid in bidiports.keys():

        domain = stpid2domain(stpid)
        vlanstr = bidiports[stpid]["vlanranges"]  # can be int-int,int-int

        idx = vlanstr.find(",")
        if idx == -1:
            # Single int or range
            (svlanid, evlanid) = parse_vlan_range(vlanstr)
            add_endpoint(endpointcount, stpid, svlanid, evlanid, domain, local_endpoints)
            endpointcount += 1
        else:
            ranges = vlanstr.split(",")
            for r in ranges:
                (svlanid, evlanid) = parse_vlan_range(r)
                add_endpoint(endpointcount, stpid, svlanid, evlanid, domain, local_endpoints)
                endpointcount += 1
    return local_endpoints


def sdp2name(inport, outport):
    # Assuming urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:ana-link-1:in is a standard
    # format, at least the beginning until 2024:
    inwords = inport.split(":")
    outwords = outport.split(":")
    name = inwords[5] + ":" + inwords[6] + "--" + outwords[5] + ":" + outwords[6]
    return name


def sdp2comp(d):
    """Return a copy of an SDP with :in and :out removed from the port identifiers"""
    d2 = copy.deepcopy(d)
    inport_id = d2["inport"]
    outport_id = d2["outport"]
    ibidiport_id = inport_id[: -len(INPORT_IN_POSTFIX)]
    obidiport_id = outport_id[: -len(OUTPORT_OUT_POSTFIX)]
    d2["inport"] = ibidiport_id
    d2["outport"] = obidiport_id
    return d2


## ChatGPT + Arno
import json


def sdp_remove_duplicates(dict_list):
    log = logger.bind()

    seen = set()
    unique_dicts = []

    for d in dict_list:
        d2 = sdp2comp(d)

        # Also test if the symmetric version is not already in seen
        sd = copy.deepcopy(d2)
        tempport = sd["inport"]
        sd["inport"] = sd["outport"]
        sd["outport"] = tempport
        # Convert dictionary to a JSON string to check for uniqueness
        dict_str = json.dumps(d2, sort_keys=True)
        sdict_str = json.dumps(sd, sort_keys=True)

        log.debug("sdp_remove_duplicates: COMP", dict_str=dict_str, sdict_str=sdict_str)

        if dict_str not in seen and sdict_str not in seen:
            seen.add(dict_str)
            unique_dicts.append(d)

    return unique_dicts


def add_link(id, linkid, name, svlanid, evlanid, domain):
    link = NetworkLink(id=id, linkid=linkid, name=name, svlanid=svlanid, evlanid=evlanid, domain=domain)
    # Put in list
    aura.state.global_links.append(link)


def nsi_reload_topology_into_links_model(sdps):
    """Take downloaded STPs and put into Endpoints
    Returns nothing
    """
    log = logger.bind()

    global links

    log.debug("nsi_reload_topology_into_links_model: Loading SDPs", sdps=sdps)
    if sdps is None or len(sdps) == 0:
        return

    unique_sdps = sdp_remove_duplicates(sdps)

    log.debug("nsi_reload_topology_into_links_model: Loading unique SDPs", sdps=sdps)

    #
    # Override default links
    #
    linkcount = 1
    aura.state.global_links = []

    for sdp in unique_sdps:
        name = sdp2name(sdp["inport"], sdp["outport"])
        domain = settings.DEFAULT_LINK_DOMAIN
        vlanstr = sdp["vlanranges"]  # can be int-int,int-int

        idx = vlanstr.find(",")
        if idx == -1:
            # Single int or range
            (svlanid, evlanid) = parse_vlan_range(vlanstr)
            add_link(linkcount, linkcount, name, svlanid, evlanid, domain)
            linkcount += 1
        else:
            ranges = vlanstr.split(",")
            for r in ranges:
                (svlanid, evlanid) = parse_vlan_range(r)
                add_link(linkcount, linkcount, name, svlanid, evlanid, domain)
                linkcount += 1


def nsi_load_parsed_soap_into_reservations_model(resdictlist):
    """Turn downloaded reservations into Model   #TODO: refactor to match nsi_load_topo or something
    Returns nothing
    """
    #
    # Override default global_reservations
    #
    aura.state.global_reservations = []

    for connid in resdictlist.keys():
        reserve_dict = resdictlist[connid]

        if (
            reserve_dict[S_RESERVATION_STATE_TAG] == NSI_RESERVATION_FAILED_STATE
            or reserve_dict[S_RESERVATION_STATE_TAG] == NSI_RESERVATION_TIMEOUT_STATE
        ):
            # Some fields missing, such as startTime
            reserve_dict[S_STARTTIME_TAG] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            reserve_dict[S_ENDTIME_TAG] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            reserve_dict[S_SOURCE_STP_TAG] = "n/a"
            reserve_dict[S_DEST_STP_TAG] = "n/a"
            reservation = Reservation(
                id=reserve_dict[FASTUID_ID_KEY],
                connectionId=connid,
                description=reserve_dict[S_DESCRIPTION_TAG],
                startTime=reserve_dict[S_STARTTIME_TAG],
                endTime=reserve_dict[S_ENDTIME_TAG],
                sourceSTP=reserve_dict[S_SOURCE_STP_TAG],
                destSTP=reserve_dict[S_DEST_STP_TAG],
                requesterNSA=reserve_dict[S_REQUESTER_NSA_TAG],
                reservationState=reserve_dict[S_RESERVATION_STATE_TAG],
                lifecycleState=reserve_dict[S_LIFECYCLE_STATE_TAG],
                dataPlaneStatus=reserve_dict[S_DATAPLANE_STATUS_TAG],
            )
        else:
            reservation = Reservation(
                id=reserve_dict[FASTUID_ID_KEY],
                connectionId=connid,
                description=reserve_dict[S_DESCRIPTION_TAG],
                startTime=reserve_dict[S_STARTTIME_TAG],
                endTime=reserve_dict[S_ENDTIME_TAG],
                sourceSTP=reserve_dict[S_SOURCE_STP_TAG],
                destSTP=reserve_dict[S_DEST_STP_TAG],
                requesterNSA=reserve_dict[S_REQUESTER_NSA_TAG],
                reservationState=reserve_dict[S_RESERVATION_STATE_TAG],
                lifecycleState=reserve_dict[S_LIFECYCLE_STATE_TAG],
                dataPlaneStatus=reserve_dict[S_DATAPLANE_STATUS_TAG],
            )

        # Put in list
        aura.state.global_reservations.append(reservation)


try:
    # DEMO: Turn topology loading off for now, so we can also demo with synthetic data,
    # which may be more comprehensible
    ONLINE = False
    # nsi_load_dds_documents()
except:
    traceback.print_exc()
    ONLINE = False

#
# Views
#


def create_footer():
    footer = c.Div(
        components=[
            c.Image(
                # src='https://avatars.githubusercontent.com/u/110818415',
                src="/static/ANA-website-footer.png",
                alt="ANA footer Logo",
                width=900,
                height=240,
                loading="lazy",
                referrer_policy="no-referrer",
                class_name="border rounded",
            )
        ]
    )
    return footer


def show_endpoints_table(heading, clickurl, local_endpoints) -> list[AnyComponent]:
    """Show a table of four endpoints, `/api` is the endpoint the frontend will connect to
    when a endpoint visits `/` to fetch components to render.
    """
    detail_url = "/endpoint-details/?id={id}"

    return [
        c.Page(  # Page provides a basic container for components
            components=[
                c.Heading(text=heading, level=2, class_name="+ text-danger"),  # renders `<h2>Endpoints</h2>`
                c.Link(components=[c.Text(text="Back")], on_click=BackEvent()),
                c.Table(
                    data=local_endpoints,
                    # define two columns for the table
                    columns=[
                        # the first is the endpoint's name rendered as a link to clickurl
                        DisplayLookup(field="name", on_click=GoToEvent(url=clickurl)),
                        # the second is the start vlan
                        DisplayLookup(field="svlanid"),
                        DisplayLookup(field="evlanid"),
                        DisplayLookup(field="domain", on_click=GoToEvent(url=detail_url)),
                    ],
                ),
                create_footer(),
            ]
        ),
    ]


def show_links_table(heading, clickurl, local_links) -> list[AnyComponent]:
    """Show a table of ANA links"""
    return [
        c.Page(  # Page provides a basic container for components
            components=add_links_table(heading, clickurl, local_links, 2)
        ),
    ]


def add_links_table(heading, clickurl, local_links, level=2) -> list[AnyComponent]:
    """Return list of components for a table of ANA links"""
    return [
        c.Heading(text=heading, level=level, class_name="+ text-danger"),
        c.Paragraph(
            text="NSI supports Explicit Route Objects (ERO), allowing link selection", class_name="+ text-success"
        ),
        c.Table(
            data=local_links,
            # define two columns for the table
            columns=[
                DisplayLookup(field="name", on_click=GoToEvent(url=clickurl)),
                DisplayLookup(field="linkid"),
            ],
        ),
        create_footer(),
    ]


def show_reservations_table(heading, clickurl, local_reservations) -> list[AnyComponent]:
    """Show a table of reservations"""
    root_url = str(settings.SERVER_URL_PREFIX) + ""  # back to landing

    return [
        c.Page(  # Page provides a basic container for components
            components=[
                c.Heading(text=heading, level=2, class_name="+ text-danger"),
                c.Link(components=[c.Paragraph(text="Back")], on_click=BackEvent()),
                c.Link(components=[c.Paragraph(text="To Landing Page")], on_click=GoToEvent(url=root_url)),
                c.Table(
                    data_model=Reservation,
                    data=local_reservations,
                    # define two columns for the table
                    columns=[
                        DisplayLookup(field="connectionId", on_click=GoToEvent(url=clickurl)),
                        DisplayLookup(field="description"),
                        DisplayLookup(field="lifecycleState"),
                    ],
                ),
                create_footer(),
            ]
        ),
    ]


def add_spans_table(heading, clickurl, local_spans) -> list[AnyComponent]:
    """Return list of components for a table of Spans"""
    return [
        c.Heading(text=heading, level=3, class_name="+ text-success"),
        c.Table(
            data_model=Span,
            data=local_spans,
            # define columns for the table
            columns=[
                DisplayLookup(field="connectionId", on_click=GoToEvent(url=clickurl)),
                DisplayLookup(field="sourceSTP"),
                DisplayLookup(field="destSTP"),
            ],
        ),
        create_footer(),
    ]


def add_discovery_table(heading, clickurl, local_discoveries, level) -> list[AnyComponent]:
    """Return list of components for a table of Spans"""
    return [
        c.Heading(text=heading, level=level, class_name="+ text-dark"),
        c.Table(
            data_model=Discovery,
            data=local_discoveries,
            # define columns for the table
            columns=[
                DisplayLookup(field="agentid", on_click=GoToEvent(url=clickurl)),
                DisplayLookup(field="version"),
                DisplayLookup(field="expires"),
            ],
        ),
        # create_footer(),
    ]
