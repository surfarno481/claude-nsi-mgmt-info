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
import datetime

#
# NSI Communications functions
# ============================
# @author: Arno Bakker
#
# No fastAPI code allowed here
#
import os
import traceback
import zlib
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4

import requests
import structlog
from lxml import etree
from urllib3.util.retry import Retry

from aura.settings import settings

logger = structlog.get_logger(__name__)

#
# Module-only variables, set by nsi_comm_init()
#
reserve_templstr = None
reserve_commit_templstr = None
reserve_abort_templstr = None
provision_templstr = None
query_summary_sync_templstr = None
query_recursive_templstr = None
terminate_templstr = None
release_templstr = None
reserve_timeout_ack_templstr = None
acknowledgement_templstr = None


def prettyprint(element, **kwargs):
    log = logger.bind()

    xml = etree.tostring(element, pretty_print=True, **kwargs)
    log.debug(xml.decode(), end="")


FIND_ANYWHERE_PREFIX = ".//"

#
# All items parsed from XML/SOAP get a numerical id about the order in which they were found
# in the XML
#
FASTUID_ID_KEY = "fastui_id"


#
# /dds/documents from DDS
#
# See https://stackoverflow.com/questions/40772297/syntaxerror-prefix-a-not-found-in-prefix-map
#
DOCUMENTS_TAG = "{http://schemas.ogf.org/nsi/2014/02/discovery/types}documents"  # aka ns2:documents
DOCUMENT_TAG = "{http://schemas.ogf.org/nsi/2014/02/discovery/types}document"  # aka ns2:document
LOCAL_TAG = "{http://schemas.ogf.org/nsi/2014/02/discovery/types}local"  # aka ns2:local
NSA_SHORT_TAG = "nsa"
TYPE_SHORT_TAG = "type"
CONTENT_SHORT_TAG = "content"
DISCOVERY_POSTFIX_MIME_TYPE = "vnd.ogf.nsi.nsa.v1+xml"  # no group/ ?
TOPOLOGY_POSTFIX_MIME_TYPE = "vnd.ogf.nsi.topology.v2+xml"


#
# /discovery XML from SuPA
#
## Metadata
NSA_TAG = "{http://schemas.ogf.org/nsi/2014/02/discovery/nsa}nsa"
NSA_ID_ATTRIB = "id"
NSA_VERSION_ATTRIB = "version"
NSA_EXPIRES_ATTRIB = "expires"


INTERFACE_TAG = "interface"
TYPE_IN_INTERFACE_TAG = "type"
HREF_IN_INTERFACE_TAG = "href"

TOPOLOGY_SERVICE_MIME_TYPE = "application/vnd.ogf.nsi.topology.v2+xml"
SOAP_PROVIDER_MIME_TYPE = "application/vnd.ogf.nsi.cs.v2.provider+soap"


#
# /topology XML from SuPA
#
SWITCHING_SERVICE_TAG = "{http://schemas.ogf.org/nml/2013/05/base#}SwitchingService"
BIDI_PORT_TAG = "{http://schemas.ogf.org/nml/2013/05/base#}BidirectionalPort"
NAME_TAG = "{http://schemas.ogf.org/nml/2013/05/base#}name"
RELATION_TAG = "{http://schemas.ogf.org/nml/2013/05/base#}Relation"
LABEL_GROUP_TAG = "{http://schemas.ogf.org/nml/2013/05/base#}LabelGroup"

INPORT_IN_POSTFIX = ":in"
OUTPORT_OUT_POSTFIX = ":out"

RELATION_HAS_INBOUND_PORT_TYPE = "http://schemas.ogf.org/nml/2013/05/base#hasInboundPort"
RELATION_HAS_OUTBOUND_PORT_TYPE = "http://schemas.ogf.org/nml/2013/05/base#hasOutboundPort"
PORTGROUP_TAG = "{http://schemas.ogf.org/nml/2013/05/base#}PortGroup"

RELATION_IS_ALIAS_TYPE = "http://schemas.ogf.org/nml/2013/05/base#isAlias"
RELATION_TYPE_ATTRIB = "type"
PORTGROUP_ID_ATTRIB = "id"

#
# NSI QUERY SOAP reply
#

# QUERY SOAP REPLY
S_RESERVATION_TAG = "reservation"
S_CONNECTION_ID_TAG = "connectionId"
S_DESCRIPTION_TAG = "description"
S_STARTTIME_TAG = "startTime"
S_ENDTIME_TAG = "endTime"
S_SOURCE_STP_TAG = "sourceSTP"
S_DEST_STP_TAG = "destSTP"
S_REQUESTER_NSA_TAG = "requesterNSA"
S_RESERVATION_STATE_TAG = "reservationState"
S_LIFECYCLE_STATE_TAG = "lifecycleState"
S_DATAPLANE_STATUS_TAG = "dataPlaneStatus"  # HACKED into value of <active>

S_QUERY_REPLY_TAGS = [
    S_RESERVATION_TAG,
    S_CONNECTION_ID_TAG,
    S_DESCRIPTION_TAG,
    S_STARTTIME_TAG,
    S_ENDTIME_TAG,
    S_SOURCE_STP_TAG,
    S_DEST_STP_TAG,
    S_REQUESTER_NSA_TAG,
    S_RESERVATION_STATE_TAG,
    S_LIFECYCLE_STATE_TAG,
    S_DATAPLANE_STATUS_TAG,
]

S_DATAPLANE_STATUS_ACTIVE_TAG = "active"

NSI_RESERVATION_FAILED_STATE = "ReserveFailed"
NSI_RESERVATION_TIMEOUT_STATE = "ReserveTimeout"

# NSI RESERVE SOAP reply
#
## S_CONNECTION_ID_TAG='connectionId'

# NSI RESERVE COMMIT SOAP reply
#
S_CORRELATION_ID_TAG = "correlationId"

S_SERVICE_EXCEPTION_TAG = "serviceException"

S_FAULTSTRING_TAG = "faultstring"


#
# NSI RESERVE async callback from Orchestrator
#
S_RESERVE_CONFIRMED_TAG = "{http://schemas.ogf.org/nsi/2013/12/connection/types}reserveConfirmed"


#
# NSI QUERY RECURSIVE async callback from Orchestrator
S_QUERY_RECURSIVE_CONFIRMED_TAG = "{http://schemas.ogf.org/nsi/2013/12/connection/types}queryRecursiveConfirmed"
S_CHILDREN_TAG = "children"
S_CHILD_TAG = "child"


def generate_uuid():
    return uuid4().urn


URN_UUID_PREFIX = "urn:uuid:"
URN_STP_PREFIX = "urn:ogf:network:example.domain:2001:topology:"
URN_STP_NAME = "name"
URN_STP_VLAN = "vlan"


# Template files currently in /static

# RESERVE
NSI_RESERVE_TEMPLATE_XMLFILE = "Reserve.xml"
NSI_RESERVE_XML_CONNECTION_PREFIX = "ANA-GRAM Connection"


# DONE: providerNSA in all msgs set to value from NSA id from /discovery

# TODO: capacity
message_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#REPLY-TO-URL#",  # http://127.0.0.1:7080/NSI/services/RequesterService2
    "#CONNECTION-DESCRIPTION#",  # string w/spaces
    "#GLOBAL-RESERVATION-ID#",  # urn:uuid:c46b7412-2263-46c6-b497-54f52e9f9ff4
    "#CONNECTION-START-TIME#",  # 2024-09-26T12:00:00+00:00  # ARNO: no timezone?
    "#CONNECTION-END-TIME#",  # 2024-09-26T22:00:00+00:00
    "#SOURCE-STP#",  # urn:ogf:network:example.domain:2001:topology:port12?vlan=1002
    "#DEST-STP#",  # urn:ogf:network:example.domain:2001:topology:port12?vlan=1002
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]


# RESERVE COMMIT
NSI_RESERVE_COMMIT_TEMPLATE_XMLFILE = "ReserveCommit.xml"

reserve_commit_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#REPLY-TO-URL#",  # http://127.0.0.1:7080/NSI/services/RequesterService2
    "#CONNECTION-ID#",  # note: no urn prefix: 2d71c50b-a6ff-46e5-8e37-567470ba832a
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]


# RESERVE ABORT
NSI_RESERVE_ABORT_TEMPLATE_XMLFILE = "ReserveAbort.xml"

reserve_abort_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#REPLY-TO-URL#",  # http://127.0.0.1:7080/NSI/services/RequesterService2
    "#CONNECTION-ID#",  # note: no urn prefix: 2d71c50b-a6ff-46e5-8e37-567470ba832a
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]


# PROVISION
NSI_PROVISION_TEMPLATE_XMLFILE = "Provision.xml"

provision_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#REPLY-TO-URL#",  # http://127.0.0.1:7080/NSI/services/RequesterService2
    "#CONNECTION-ID#",  # note: no urn prefix: 2d71c50b-a6ff-46e5-8e37-567470ba832a
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]

# TERMINATE
NSI_TERMINATE_TEMPLATE_XMLFILE = "Terminate.xml"

terminate_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#REPLY-TO-URL#",  # http://127.0.0.1:7080/NSI/services/RequesterService2
    "#CONNECTION-ID#",  # note: no urn prefix: 2d71c50b-a6ff-46e5-8e37-567470ba832a
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]


# RELEASE
NSI_RELEASE_TEMPLATE_XMLFILE = "Release.xml"

release_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#REPLY-TO-URL#",  # http://127.0.0.1:7080/NSI/services/RequesterService2
    "#CONNECTION-ID#",  # note: no urn prefix: 2d71c50b-a6ff-46e5-8e37-567470ba832a
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]


# RESERVE_TIMEOUT_ACK
NSI_RESERVE_TIMEOUT_ACK_TEMPLATE_XMLFILE = "ReserveTimeoutACK.xml"

reserve_timeout_ack_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#REPLY-TO-URL#",  # http://127.0.0.1:7080/NSI/services/RequesterService2
    "#CONNECTION-ID#",  # note: no urn prefix: 2d71c50b-a6ff-46e5-8e37-567470ba832a
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]

# ACKNOWLEDGEMENT
NSI_ACKNOWLEDGEMENT_TEMPLATE_XMLFILE = "GenericAcknowledgement.xml"

acknowledgement_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]

# QUERY
NSI_QUERY_SUMMARY_SYNC_TEMPLATE_XMLFILE = "QuerySummarySync.xml"

# TODO
#      <connectionId>af7e02ef-608a-42d7-89b3-9f701051a58e</connectionId>
#      <ifModifiedSince>2022-09-01T14:50:46.767879+00:00</ifModifiedSince>
#     <globalReservationId>76cc6c3c-a126-4174-8016-11f00012ec1d</globalReservationId>
query_summary_sync_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#CONNECTION-ID#",  # note: no urn prefix: 2d71c50b-a6ff-46e5-8e37-567470ba832a
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]


# QUERY_RECURSIVE
NSI_QUERY_RECURSIVE_TEMPLATE_XMLFILE = "QueryRecursive.xml"

query_recursive_keys = [
    "#CORRELATION-ID#",  # urn:uuid:a3eb6740-7227-473b-af6f-6705d489407c
    "#REPLY-TO-URL#",  # http://127.0.0.1:7080/NSI/services/RequesterService2
    "#CONNECTION-ID#",  # note: no urn prefix: 2d71c50b-a6ff-46e5-8e37-567470ba832a
    "#PROVIDER-NSA-ID#",  # urn:ogf:network:example.domain:2001:nsa:supa
]


def stp_dict_to_urn(stp_dict):
    return stp_dict[URN_STP_NAME] + "?" + URN_STP_VLAN + "=" + str(stp_dict[URN_STP_VLAN])


def generate_reserve_xml(
    message_templstr,
    correlation_uuid_py,
    reply_to_url,
    connection_descr,
    global_reservation_uuid_py,
    start_datetime_py,
    end_datetime_py,
    source_stp_dict,
    dest_stp_dict,
    provider_nsa_id,
):
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)
    global_reservation_urn = URN_UUID_PREFIX + str(global_reservation_uuid_py)
    start_time_str = start_datetime_py.isoformat()
    end_time_str = end_datetime_py.isoformat()

    source_stp_str = stp_dict_to_urn(source_stp_dict)
    dest_stp_str = stp_dict_to_urn(dest_stp_dict)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#REPLY-TO-URL#"] = reply_to_url
    message_dict["#CONNECTION-DESCRIPTION#"] = connection_descr
    message_dict["#GLOBAL-RESERVATION-ID#"] = global_reservation_urn
    message_dict["#CONNECTION-START-TIME#"] = start_time_str
    message_dict["#CONNECTION-END-TIME#"] = end_time_str
    message_dict["#SOURCE-STP#"] = source_stp_str
    message_dict["#DEST-STP#"] = dest_stp_str
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in message_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml


def generate_reserve_commit_xml(message_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id):
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#REPLY-TO-URL#"] = reply_to_url
    message_dict["#CONNECTION-ID#"] = connid_str
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in reserve_commit_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml


def generate_reserve_abort_xml(message_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id):
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#REPLY-TO-URL#"] = reply_to_url
    message_dict["#CONNECTION-ID#"] = connid_str
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in reserve_commit_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml


def generate_provision_xml(message_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id):
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#REPLY-TO-URL#"] = reply_to_url
    message_dict["#CONNECTION-ID#"] = connid_str
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in provision_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml


def generate_terminate_xml(message_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id):
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#REPLY-TO-URL#"] = reply_to_url
    message_dict["#CONNECTION-ID#"] = connid_str
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in terminate_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml


def generate_release_xml(message_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id):
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#REPLY-TO-URL#"] = reply_to_url
    message_dict["#CONNECTION-ID#"] = connid_str
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in terminate_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml


def generate_reserve_timeout_ack_xml(message_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id):
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#REPLY-TO-URL#"] = reply_to_url
    message_dict["#CONNECTION-ID#"] = connid_str
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in terminate_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml


def generate_acknowledgement_xml(message_templstr, correlation_uuid_py, provider_nsa_id):
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in acknowledgement_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml


def generate_query_summary_sync_xml(message_templstr, correlation_uuid_py, connid_str, provider_nsa_id):
    # Generate values
    log = logger.bind()

    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#CONNECTION-ID#"] = connid_str
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in query_summary_sync_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    log.debug("QUERY_XML", message_xml=message_xml)
    return message_xml


def generate_query_recursive_xml(message_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id):
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {}
    message_dict["#CORRELATION-ID#"] = correlation_urn
    message_dict["#REPLY-TO-URL#"] = reply_to_url
    message_dict["#CONNECTION-ID#"] = connid_str
    message_dict["#PROVIDER-NSA-ID#"] = provider_nsa_id

    message_xml = message_templstr
    for message_key in terminate_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml


#
# Library
#

requests_session_adapter = requests.adapters.HTTPAdapter(max_retries=Retry(connect=3, backoff_factor=0.1))
session = requests.Session()
session.mount("http://", requests_session_adapter)
session.mount("https://", requests_session_adapter)


def nsi_comm_init(templ_absdir):
    """Initialise NSI communications."""
    # Getting Max Retry errors? Due to passphrase protected private key
    # https://stackoverflow.com/questions/23013220/max-retries-exceeded-with-url-in-requests
    log = logger.bind()

    # TODO: this is currently called from aura/__init__.py which causes it to be called twice.
    log.debug("NSI-COMM-INIT: loading templates")
    #
    # Load SOAP templates
    #
    global reserve_templstr
    global reserve_commit_templstr
    global reserve_abort_templstr
    global provision_templstr
    global query_summary_sync_templstr
    global query_recursive_templstr
    global terminate_templstr
    global release_templstr
    global reserve_timeout_ack_templstr
    global acknowledgement_templstr

    # RESERVE
    reserve_templpath = os.path.join(templ_absdir, NSI_RESERVE_TEMPLATE_XMLFILE)

    # Read Reserve template code
    with open(reserve_templpath) as reserve_templfile:
        reserve_templstr = reserve_templfile.read()

    # RESERVE-COMMIT
    reserve_commit_templpath = os.path.join(templ_absdir, NSI_RESERVE_COMMIT_TEMPLATE_XMLFILE)

    # Read Reserve Commit template code
    with open(reserve_commit_templpath) as reserve_commit_templfile:
        reserve_commit_templstr = reserve_commit_templfile.read()

    # RESERVE-ABORT
    reserve_abort_templpath = os.path.join(templ_absdir, NSI_RESERVE_ABORT_TEMPLATE_XMLFILE)

    # Read Reserve Abort template code
    with open(reserve_abort_templpath) as reserve_abort_templfile:
        reserve_abort_templstr = reserve_abort_templfile.read()

    # PROVISION
    provision_templpath = os.path.join(templ_absdir, NSI_PROVISION_TEMPLATE_XMLFILE)

    # Read Reserve template code
    with open(provision_templpath) as provision_templfile:
        provision_templstr = provision_templfile.read()

    # QUERY SUMMARY SYNC
    query_summary_sync_templpath = os.path.join(templ_absdir, NSI_QUERY_SUMMARY_SYNC_TEMPLATE_XMLFILE)

    # Read Reserve template code
    with open(query_summary_sync_templpath) as query_summary_sync_templfile:
        query_summary_sync_templstr = query_summary_sync_templfile.read()

    # QUERY RECURSIVE to get path details
    query_recursive_templpath = os.path.join(templ_absdir, NSI_QUERY_RECURSIVE_TEMPLATE_XMLFILE)

    # Read RESERVE_TIMEOUT_ACK template code
    with open(query_recursive_templpath) as query_recursive_templfile:
        query_recursive_templstr = query_recursive_templfile.read()

    # TERMINATE
    terminate_templpath = os.path.join(templ_absdir, NSI_TERMINATE_TEMPLATE_XMLFILE)

    # Read TERMINATE template code
    with open(terminate_templpath) as terminate_templfile:
        terminate_templstr = terminate_templfile.read()

    # RELEASE
    release_templpath = os.path.join(templ_absdir, NSI_RELEASE_TEMPLATE_XMLFILE)

    # Read RELEASE template code
    with open(release_templpath) as release_templfile:
        release_templstr = release_templfile.read()

    # RESERVE_TIMEOUT_ACK
    reserve_timeout_ack_templpath = os.path.join(templ_absdir, NSI_RESERVE_TIMEOUT_ACK_TEMPLATE_XMLFILE)

    # Read RESERVE_TIMEOUT_ACK template code
    with open(reserve_timeout_ack_templpath) as reserve_timeout_ack_templfile:
        reserve_timeout_ack_templstr = reserve_timeout_ack_templfile.read()

    # ACKNOWLEDGEMENT
    acknowledgement_templpath = os.path.join(templ_absdir, NSI_ACKNOWLEDGEMENT_TEMPLATE_XMLFILE)

    # Read ACKNOWLEDGEMENT template code
    with open(acknowledgement_templpath) as acknowledgement_templfile:
        acknowledgement_templstr = acknowledgement_templfile.read()


def nsi_util_get_and_parse_xml(url):
    xml = nsi_util_get_xml(url)
    if xml is None:
        return xml
    return nsi_util_parse_xml(xml)


def nsi_util_get_xml(url):
    log = logger.bind()

    # throws Exception to higher layer for display to user
    log.debug("SENDING HTTP REQUEST FOR XML", url=str(url))
    # 2024-11-08: SuPA moxy currently has self-signed certificate
    r = session.get(
        url,
        verify=(
            settings.CERTIFICATES_DIRECTORY
            if settings.VERIFY_REQUESTS and settings.CERTIFICATES_DIRECTORY
            else settings.VERIFY_REQUESTS
        ),
        cert=(settings.NSI_AURA_CERTIFICATE, settings.NSI_AURA_PRIVATE_KEY),
    )
    # logger.debug log.debug(r.status_code)
    # logger.debug log.debug(r.headers['content-type'])
    # logger.debug log.debug(r.encoding)
    log.debug(r.status_code)
    log.debug(r.headers["content-type"])
    log.debug(r.encoding)
    log.debug(r.content)
    # except:
    #    log.debug("nsi_util_get_and_parse_xml: error talking to "+url,file=sys.stderr)
    #    traceback.print_exc()
    #    return None

    content_type = r.headers["content-type"]
    content_type = content_type.lower()  # UTF-8 and utf-8
    if content_type == "application/xml" or content_type.startswith("text/xml"):
        return r.content
    log.debug(str(url) + " did not return XML, but " + r.headers["content-type"])
    return None


def nsi_util_parse_xml(xml):
    """Parse XML
    return etree
    """
    xml_file = BytesIO(xml)
    tree = etree.parse(xml_file)
    return tree


#
# Example dicts
#
# {'Header': {'nsiHeader': {'correlationId': UUID('4f0a4f6b-1187-4670-b451-bb8005105ba5'),
#                           'pathTrace': {'connectionId': UUID('1153d8ed-f97b-4f01-b529-af8080980ea9'),
#                                         'id': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari',
#                                         'path': {'segment': {'connectionId': UUID('60a998cd-4295-4253-b8b8-4f5c8edd9891'),
#                                                              'id': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:nsa:supa',
#                                                              'order': '0'}}},
#                           'protocolVersion': 'application/vnd.ogf.nsi.cs.v2.requester+soap',
#                           'providerNSA': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari',
#                           'requesterNSA': 'urn:ogf:network:anaeng.global:2024:nsa:nsi-aura'}},
#  'Body': {'reserveConfirmed': {'connectionId': UUID('1153d8ed-f97b-4f01-b529-af8080980ea9'),
#                                'criteria': {'p2ps': {'capacity': '1000',
#                                                      'destSTP': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1?vlan=147',
#                                                      'directionality': 'Bidirectional',
#                                                      'sourceSTP': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1?vlan=3762',
#                                                      'symmetricPath': 'true'},
#                                             'schedule': {'endTime': datetime.datetime(2025, 2, 26, 11, 1, tzinfo=datetime.timezone.utc),
#                                                          'startTime': datetime.datetime(2025, 2, 26, 10, 59, tzinfo=datetime.timezone.utc)},
#                                             'serviceType': 'http://services.ogf.org/nsi/2013/12/descriptions/EVTS.A-GOLE',
#                                             'version': '1'}}}}
#
#
# {'Header': {'nsiHeader': {'correlationId': UUID('4ab41cb2-8b04-4ba9-9c68-e736b9091b2e'),
#                           'protocolVersion': 'application/vnd.ogf.nsi.cs.v2.requester+soap',
#                           'providerNSA': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari',
#                           'requesterNSA': 'urn:ogf:network:anaeng.global:2024:nsa:nsi-aura'}},
#  'Body': {'reserveCommitConfirmed': {'connectionId': UUID('1153d8ed-f97b-4f01-b529-af8080980ea9')}}}
#
#
# {'Header': {'nsiHeader': {'protocolVersion': 'application/vnd.ogf.nsi.cs.v2.requester+soap',
#                           'correlationId': UUID('620d1ce7-bce5-48f9-b12f-c6e7c42e2054'),
#                           'requesterNSA': 'urn:ogf:network:anaeng.global:2024:nsa:nsi-aura',
#                           'providerNSA': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari'}},
#  'Body': {'reserveFailed': {'connectionId': UUID('6572756a-141c-4179-bd58-94abdd93589e'),
#                             'connectionStates': {'reservationState': 'ReserveFailed',
#                                                  'provisionState': 'Released',
#                                                  'lifecycleState': 'Created',
#                                                  'dataPlaneStatus': {'active': 'false',
#                                                                      'version': '0',
#                                                                      'versionConsistent': 'false'}},
#                             'serviceException': {'nsaId': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari',
#                                                  'errorId': '00502',
#                                                  'text': 'Child connection segment error is present',
#                                                  'variables': {},
#                                                  'childException': {'nsaId': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:nsa:supa',
#                                                                     'connectionId': UUID('e4fb92a9-7169-4b8a-a1c3-3981211e88dd'),
#                                                                     'serviceType': {},
#                                                                     'errorId': '00704',
#                                                                     'text': 'STP_UNAVALABLE: Specified STP already '
#                                                                             'in use. (no matching VLAN found '
#                                                                             '(requested: 3762, available: 3764-3769)',
#                                                                     'variables': {'variable': {'namespace': 'http://schemas.ogf.org/nsi/2013/12/services/point2point',
#                                                                                                'type': 'sourceSTP',
#                                                                                                'value': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1?vlan=3762'}}}}}}}
#
#
# {'Header': {'nsiHeader': {'protocolVersion': 'application/vnd.ogf.nsi.cs.v2.provider+soap',
#                           'correlationId': UUID('53100ae8-3544-434d-8f42-ea0e1f0951d8'),
#                           'requesterNSA': 'urn:ogf:network:anaeng.global:2024:nsa:nsi-aura',
#                           'providerNSA': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari'}},
#  'Body': {'Fault': {'faultcode': 'soapenv:Server',
#                     'faultstring': 'Connection state machine is in invalid state for received message',
#                     'detail': {'serviceException': {'nsaId': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari',
#                                                     'errorId': '00201',
#                                                     'text': 'Connection state machine is in invalid state for '
#                                                             'received message',
#                                                     'variables': {}}}}}}
#
#
# {'Header': {'nsiHeader': {'protocolVersion': 'application/vnd.ogf.nsi.cs.v2.requester+soap',
#                           'correlationId': UUID('2e4cb8d7-41f8-4133-aab5-59369f42b088'),
#                           'requesterNSA': 'urn:ogf:network:anaeng.global:2024:nsa:nsi-aura',
#                           'providerNSA': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari'}},
#  'Body': {'errorEvent': {'connectionId': UUID('0e092969-c8f7-4f2f-b115-6271fd5a87f7'),
#                          'notificationId': '1',
#                          'timeStamp': datetime.datetime(2025, 2, 26, 11, 13, 0, 344533, tzinfo=datetime.timezone.utc),
#                          'event': 'activateFailed',
#                          'originatingConnectionId': 'ff484dde-b9c8-4ec9-b863-f3d9c9fe2b3c',
#                          'originatingNSA': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:nsa:supa',
#                          'additionalInfo': {},
#                          'serviceException': {'nsaId': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari',
#                                               'connectionId': UUID('0e092969-c8f7-4f2f-b115-6271fd5a87f7'),
#                                               'serviceType': {},
#                                               'errorId': '00800',
#                                               'text': 'GENERIC_RM_ERROR: An internal (N)RM error has caused a '
#                                                       'message processing failure.',
#                                               'childException': {'nsaId': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:nsa:supa',
#                                                                  'connectionId': UUID('ff484dde-b9c8-4ec9-b863-f3d9c9fe2b3c'),
#                                                                  'serviceType': {},
#                                                                  'errorId': '00800',
#                                                                  'text': 'GENERIC_RM_ERROR: An internal (N)RM error '
#                                                                          'has caused a message processing failure. ',
#                                                                  'variables': {}}}}}}
#
# {'Header': {'nsiHeader': {'protocolVersion': 'application/vnd.ogf.nsi.cs.v2.requester+soap',
#                           'correlationId': UUID('5f4f77fe-22cf-4a5e-aecf-d4b7dd291c50'),
#                           'requesterNSA': 'urn:ogf:network:anaeng.global:2024:nsa:nsi-aura',
#                           'providerNSA': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari'}},
#  'Body': {'dataPlaneStateChange': {'connectionId': UUID('8c5bac21-336e-47b0-8479-1c7e3fba21d1'),
#                                    'notificationId': '1',
#                                    'timeStamp': datetime.datetime(2025, 2, 27, 16, 3, 28, 414707, tzinfo=datetime.timezone.utc),
#                                    'dataPlaneStatus': {'active': 'true',
#                                                        'version': '1',
#                                                        'versionConsistent': 'true'}}}}
#
# {'Body': {'querySummarySyncConfirmed': {'lastModified': '2025-04-10T15:46:41.233Z',
#                                         'reservation': {'connectionId': UUID('aae5c739-a735-4a94-bb18-2640a43f718e'),
#                                                         'connectionStates': {'dataPlaneStatus': {'active': 'true',
#                                                                                                  'version': '1',
#                                                                                                  'versionConsistent': 'true'},
#                                                                              'lifecycleState': 'Created',
#                                                                              'provisionState': 'Provisioned',
#                                                                              'reservationState': 'ReserveStart'},
#                                                         'criteria': {'children': {'child': [{'connectionId': UUID('19672f49-1dba-4e4f-8251-73fa8eea140f'),
#                                                                                              'order': '0',
#                                                                                              'p2ps': {'capacity': '1000',
#                                                                                                       'destSTP': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1?vlan=1360',
#                                                                                                       'directionality': 'Bidirectional',
#                                                                                                       'sourceSTP': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1?vlan=3762',
#                                                                                                       'symmetricPath': 'true'},
#                                                                                              'providerNSA': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:nsa:supa',
#                                                                                              'serviceType': 'http://services.ogf.org/nsi/2013/12/descriptions/EVTS.A-GOLE'},
#                                                                                             {'connectionId': UUID('f30fd726-cd86-41ee-8876-6199090b8b21'),
#                                                                                              'order': '1',
#                                                                                              'p2ps': {'capacity': '1000',
#                                                                                                       'destSTP': 'urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1?vlan=444',
#                                                                                                       'directionality': 'Bidirectional',
#                                                                                                       'sourceSTP': 'urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:ana-link-1?vlan=1360',
#                                                                                                       'symmetricPath': 'true'},
#                                                                                              'providerNSA': 'urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:nsa:supa',
#                                                                                              'serviceType': 'http://services.ogf.org/nsi/2013/12/descriptions/EVTS.A-GOLE'}]},
#                                                                      'p2ps': {'capacity': '1000',
#                                                                               'destSTP': 'urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1?vlan=444',
#                                                                               'directionality': 'Bidirectional',
#                                                                               'sourceSTP': 'urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1?vlan=3762',
#                                                                               'symmetricPath': 'true'},
#                                                                      'schedule': {'endTime': datetime.datetime(2045, 3, 16, 15, 32, 21, 30175, tzinfo=datetime.timezone.utc),
#                                                                                   'startTime': datetime.datetime(2025, 4, 10, 15, 32, 21, 30155, tzinfo=datetime.timezone.utc)},
#                                                                      'serviceType': 'http://services.ogf.org/nsi/2013/12/descriptions/EVTS.A-GOLE',
#                                                                      'version': '1'},
#                                                         'description': 'test '
#                                                                        '001',
#                                                         'requesterNSA': 'urn:ogf:network:anaeng.global:2024:nsa:nsi-aura'}}},
#  'Header': {'nsiHeader': {'correlationId': UUID('d665fb22-2ffc-499d-b2b4-9804f3becb4c'),
#                           'protocolVersion': 'application/vnd.ogf.nsi.cs.v2.provider+soap',
#                           'providerNSA': 'urn:ogf:network:ana.dlp.surfnet.nl:2024:nsa:safnari',
#                           'requesterNSA': 'urn:ogf:network:anaeng.global:2024:nsa:nsi-aura'}}}


def nsi_util_element_to_dict(node, attributes=True):
    """Convert an lxml.etree node tree into a dict."""
    result = {}
    if attributes:
        for item in node.attrib.items():
            key, result[key] = item

    for element in node.iterchildren():
        # Remove namespace prefix
        key = etree.QName(element).localname

        # Process element as tree element if the inner XML contains non-whitespace content
        if element.text and element.text.strip():
            if key in ("connectionId", "correlationId"):
                value = UUID(element.text)
            elif key in ("timeStamp", "startTime", "endTime"):
                value = datetime.fromisoformat(element.text)
            else:
                value = element.text
        else:
            value = nsi_util_element_to_dict(element)
        # Create a list of values for multiple identical keys
        if key in result:
            if type(result[key]) is list:
                result[key].append(value)
            else:
                result[key] = [result[key], value]
        else:
            result[key] = value
    return result


def nsi_util_xml_to_dict(xml: bytes) -> dict[Any, Any]:
    """Convert XML string to dict."""
    return nsi_util_element_to_dict(etree.fromstring(xml))


# Read discover information, return dict with found services
def nsi_get_dds_documents(url):
    """Returns a dictionary with:
    "local" : a discovery dictionary for the NSI Orchestrator / Safnari
    "documents" : a dictionary of documents, one per NSA-ID mentioned.
    Typically there is a topology and a discovery document, which are decoded
    into dictionaries, and put in document["discovery"] and document["topology"].

    TODO: All topology data from all uPAs is downloaded in one go. Will this scale?
    """
    log = logger.bind()

    # REPLACE
    # with open(os.path.join("samples","dds.xml")) as dds_file:
    #    tree = etree.parse(dds_file)
    # dds_file.close()

    local = {}
    local["metadata"] = {}
    local["services"] = {}
    documents = {}

    tree = nsi_util_get_and_parse_xml(url)
    # Throws Exception

    root = tree.getroot()

    for element in root.iter():
        log.debug(f"nsi_get_dds_documents: ROOT FOUND {element.tag} - {element.text} --- {element.attrib}")

    # Store documents
    # Find all document tags
    ###element = tree.find(FIND_ANYWHERE_PREFIX+DOCUMENTS_TAG)

    # Arno: I see the top-level documents tag, but cannot get it using find
    # tag = tree.find(FIND_ANYWHERE_PREFIX+DOCUMENTS_TAG)
    for tag in root.iter():
        if tag.tag == DOCUMENTS_TAG:
            element = tag
            break

    for tag in element.findall(FIND_ANYWHERE_PREFIX + DOCUMENT_TAG):

        log.debug(f"nsi_get_dds_documents FOUND document {tag.tag} - {tag.text} --- {tag.attrib}")
        nsa = tag.find(FIND_ANYWHERE_PREFIX + NSA_SHORT_TAG)
        type = tag.find(FIND_ANYWHERE_PREFIX + TYPE_SHORT_TAG)
        content = tag.find(FIND_ANYWHERE_PREFIX + CONTENT_SHORT_TAG)

        # Data is distributed, so we need to build a database that we fill in as we parse pieces
        nsa_id = nsa.text
        if nsa_id not in documents:
            documents[nsa_id] = {"discovery": None, "topology": None}

        # Piece of puzzle?
        if type.text == DISCOVERY_POSTFIX_MIME_TYPE or type.text == TOPOLOGY_POSTFIX_MIME_TYPE:

            gzipped = base64.b64decode(content.text)
            # See https://stackoverflow.com/questions/2695152/in-python-how-do-i-decode-gzip-encoding
            xml = zlib.decompress(gzipped, 16 + zlib.MAX_WBITS)

            tree2 = nsi_util_parse_xml(xml)
            # Throws exception

            if type.text == DISCOVERY_POSTFIX_MIME_TYPE:
                disc_dict = nsi_parse_discovery_xml_tree(tree2)
                # Sanity check: compare nsa.text to ["metadata"]["id"]
                # log.debug("GET DOCUMENTS: COMPARE",nsa.text)
                log.debug("nsi_get_dds_documents: DISC", disc_dict=disc_dict)

                documents[nsa_id]["discovery"] = disc_dict

            elif type.text == TOPOLOGY_POSTFIX_MIME_TYPE:
                topo_dict = nsi_parse_topology_sdp_xml_tree(tree2)
                # Sanity check: compare nsa.text to ["metadata"]["id"]
                # log.debug("GET DOCUMENTS: COMPARE",nsa.text)
                log.debug("nsi_get_dds_documents: TOPO", topo_dict=topo_dict)

                documents[nsa_id]["topology"] = topo_dict

    complete_documents = {}
    for nsa_id in documents.keys():
        document = documents[nsa_id]
        log.debug("nsi_get_dds_documents: COMPLETE?", document=document)
        # Add to set when info complete
        if document["discovery"] is not None and document["topology"] is not None:

            nsa_id = document["discovery"]["metadata"][NSA_ID_ATTRIB]
            log.debug("nsi_get_dds_documents: ADDING DOC", nsa_id=nsa_id)
            complete_documents[nsa_id] = document

    #
    # Decode ns2:local entry, which points to the Orchestrator/Safnari
    #
    # Arno: CHECK I see the top-level documents tag, but cannot get it using find
    ##tag = tree.find(FIND_ANYWHERE_PREFIX+LOCAL_TAG)
    # tag = tree.find(FIND_ANYWHERE_PREFIX+DOCUMENTS_TAG)
    for element in root.iter():
        if element.tag == LOCAL_TAG:
            tag = element
            break

    nsa = tag.find(FIND_ANYWHERE_PREFIX + NSA_SHORT_TAG)
    type = tag.find(FIND_ANYWHERE_PREFIX + TYPE_SHORT_TAG)
    content = tag.find(FIND_ANYWHERE_PREFIX + CONTENT_SHORT_TAG)

    if type.text == DISCOVERY_POSTFIX_MIME_TYPE:

        gzipped = base64.b64decode(content.text)
        # See https://stackoverflow.com/questions/2695152/in-python-how-do-i-decode-gzip-encoding
        xml = zlib.decompress(gzipped, 16 + zlib.MAX_WBITS)

        tree2 = nsi_util_parse_xml(xml)
        # Throws exception

        local = nsi_parse_discovery_xml_tree(tree2)
        # Sanity check: compare nsa.text to ["metadata"]["id"]
        # log.debug("GET DOCUMENTS: COMPARE",nsa.text)
        log.debug("GET DOCUMENT: ORCH local", local=local)

    ret_dict = {"local": local, "documents": complete_documents}
    return ret_dict


# Read discover information, return dict with found services
def nsi_get_discovery(url):
    """Returns a discovery dictionary with:
    "metadata": info about the topology
    "services": Key is the MIME type, value the URL
    """
    xml = nsi_util_get_xml(url)
    # throws Exception to higher level

    tree = nsi_util_parse_xml(xml)
    # throws Exception to higher level

    return nsi_parse_discovery_xml_tree(tree)


def nsi_parse_discovery_xml_tree(tree):
    """Get discovery dict from tree"""
    log = logger.bind()

    metadata = {}
    metadata[NSA_ID_ATTRIB] = None
    metadata[NSA_VERSION_ATTRIB] = None
    metadata[NSA_EXPIRES_ATTRIB] = None
    services = {}

    root = tree.getroot()

    # for element in root.iter():
    #    log.debug(f"#FOUND {element.tag} - {element.text} --- {element.attrib}")

    # Store metadata

    # Arno: I see the top-level NSA tag, but cannot get it using find
    # tag = tree.find(FIND_ANYWHERE_PREFIX+NSA_TAG)
    # tag = tree.find(FIND_ANYWHERE_PREFIX+"nsa:nsa")
    # tag = tree.find("nsa:nsa")
    # tag = tree.find(FIND_ANYWHERE_PREFIX+NSA_TAG+":nsa")
    for element in root.iter():
        if element.tag == NSA_TAG:
            tag = element
            break

    # log.debug("TOPO NSA list",tag)
    # log.debug("TOPO NSA attribs",tag.attrib)

    metadata[NSA_ID_ATTRIB] = tag.attrib[NSA_ID_ATTRIB]
    metadata[NSA_VERSION_ATTRIB] = tag.attrib[NSA_VERSION_ATTRIB]
    metadata[NSA_EXPIRES_ATTRIB] = tag.attrib[NSA_EXPIRES_ATTRIB]
    # TODO more info

    # log.debug("TOPO META",metadata)

    # Find all interface tags
    for element in tree.findall(FIND_ANYWHERE_PREFIX + INTERFACE_TAG):
        log.debug(f"#FOUND interface {element.tag} - {element.text} --- {element.attrib}")
        itype = element.find(FIND_ANYWHERE_PREFIX + TYPE_IN_INTERFACE_TAG)
        href = element.find(FIND_ANYWHERE_PREFIX + HREF_IN_INTERFACE_TAG)
        log.debug("SERVICE", text=itype.text, href=href.text)
        services[itype.text] = href.text

    disc_dict = {"metadata": metadata, "services": services}
    return disc_dict


# Read discover information, return dict with found services
def nsi_get_discovery(url):
    """Returns a discovery dictionary with:
    "metadata": info about the topology
    "services": Key is the MIME type, value the URL
    """
    log = logger.bind()

    metadata = {}
    metadata[NSA_ID_ATTRIB] = None
    metadata[NSA_VERSION_ATTRIB] = None
    metadata[NSA_EXPIRES_ATTRIB] = None
    services = {}
    disc_dict = {"metadata": metadata, "services": services}

    tree = nsi_util_get_and_parse_xml(url)
    if tree is None:
        return disc_dict

    root = tree.getroot()

    # for element in root.iter():
    #    log.debug(f"#FOUND {element.tag} - {element.text} --- {element.attrib}")

    # Store metadata

    # Arno: I see the top-level NSA tag, but cannot get it using find
    # tag = tree.find(FIND_ANYWHERE_PREFIX+NSA_TAG)
    # tag = tree.find(FIND_ANYWHERE_PREFIX+"nsa:nsa")
    # tag = tree.find("nsa:nsa")
    # tag = tree.find(FIND_ANYWHERE_PREFIX+NSA_TAG+":nsa")
    for element in root.iter():
        if element.tag == NSA_TAG:
            tag = element
            break

    # log.debug("TOPO NSA list",tag)
    # log.debug("TOPO NSA attribs",tag.attrib)

    metadata[NSA_ID_ATTRIB] = tag.attrib[NSA_ID_ATTRIB]
    metadata[NSA_VERSION_ATTRIB] = tag.attrib[NSA_VERSION_ATTRIB]
    metadata[NSA_EXPIRES_ATTRIB] = tag.attrib[NSA_EXPIRES_ATTRIB]
    # TODO more info

    # log.debug("TOPO META",metadata)

    # Find all interface tags
    for element in tree.findall(FIND_ANYWHERE_PREFIX + INTERFACE_TAG):
        log.debug(f"#FOUND interface {element.tag} - {element.text} --- {element.attrib}")
        itype = element.find(FIND_ANYWHERE_PREFIX + TYPE_IN_INTERFACE_TAG)
        href = element.find(FIND_ANYWHERE_PREFIX + HREF_IN_INTERFACE_TAG)
        log.debug("SERVICE", itype=itype.text, href=href.text)
        services[itype.text] = href.text

    disc_dict = {"metadata": metadata, "services": services}
    return disc_dict


# Read topology.xml from SuPA
def nsi_get_topology(url):
    """Returns a dictionary of STPs (=Qualified STP, Unqualified STP, SDP)
    Key is the id. Values are:
    fastui_id: int, in the order found in XML
    vlanranges: int or int-int (qualified, vs unqualified) or int-int,int-int

    Ignores STP vs SDP, no longer used.
    """
    xml = nsi_util_get_xml(url)
    # throws Exception to higher level

    tree = nsi_util_parse_xml(xml)
    # throws Exception to higher level

    return nsi_parse_topology_xml_tree(tree)


def nsi_parse_topology_xml_tree(tree):
    """Find all BidirectionalPorts, ignoring STP vs SDP. No longer used."""
    log = logger.bind()

    # Find all BidirectionalPort tags
    bidiports = {}

    bidicount = 1
    for element in tree.findall(FIND_ANYWHERE_PREFIX + BIDI_PORT_TAG):
        # logger.debug log.debug(f"#FOUND PortGroup {element.tag} - {element.text} --- {element.attrib}")
        bidiport_id = element.attrib["id"]
        name = next(name.text for name in element.iter(NAME_TAG))
        bidiports[bidiport_id] = {FASTUID_ID_KEY: bidicount, "name": name}  # id for fastui
        bidicount += 1

    # logger.debug log.debug("#BIDIPORTS",bidiports)

    # Find Relation hasInbountPort, which contains PortGroups that have the VLANS per unidirectional STP,
    # i.e., bidi + ":in". I consider those to be the same as the outbond ones.

    for element in tree.findall(FIND_ANYWHERE_PREFIX + RELATION_TAG):
        # log.debug(f"#FOUND2 Relation {element.tag} - {element.text} --- {element.attrib}")
        if element.attrib["type"] == RELATION_HAS_INBOUND_PORT_TYPE:

            # logger.debug log.debug("#hasINBOUNDPORT")
            # for inport in element.find(FIND_ANYWHERE_PREFIX+PORTGROUP_TAG):
            for inport in element.iterfind(FIND_ANYWHERE_PREFIX + PORTGROUP_TAG):

                # logger.debug log.debug("#INBOUND PORTGROUP",inport.attrib)

                # ISSUE: also matches PortGroup isAlias within

                if inport is not None:
                    inport_id = inport.attrib["id"]  # this is the bidiport_id + ":in"
                    bidiport_id = inport_id[: -len(INPORT_IN_POSTFIX)]

                    # logger.debug log.debug("INPORT",bidiport_id)

                    lg = inport.find(FIND_ANYWHERE_PREFIX + LABEL_GROUP_TAG)
                    # logger.debug log.debug("LABELGROUP",lg)
                    if lg is not None:
                        # logger.debug log.debug("#VLANS",lg.text)
                        vlanstr = lg.text

                    if inport is not None and lg is not None:
                        try:
                            bidi_dict = bidiports[bidiport_id]
                            bidi_dict["vlanranges"] = vlanstr
                        except KeyError:
                            traceback.print_exc()

    return bidiports


# Read topology.xml from NSI-DDS
#
# TODO: complete & test
#
def nsi_get_topology_sdp(url):
    """Returns a dictionary of STPs (=Qualified STP, Unqualified STP, SDP)
    Key is the id. Values are:
    fastui_id: int, in the order found in XML
    vlanranges: int or int-int (qualified, vs unqualified) or int-int,int-int
    TODO: flag for SDP
    """
    xml = nsi_util_get_xml(url)
    # throws Exception to higher level

    tree = nsi_util_parse_xml(xml)
    # throws Exception to higher level

    return nsi_parse_topology_sdp_xml_tree(tree)


def nsi_parse_topology_sdp_xml_tree(tree):
    """Find all STP and SDPs in the tree
    Returns: a dictionary:
    "stps" : all BiDirectionalPorts (in variant), a dictionary indexed by port id
    "sdps" : all BiDirectionalPorts linked via isAlias, a list with "inport","outport" and "vlanranges"
    """
    log = logger.bind()

    # Find all BidirectionalPort tags
    bidiports = {}

    bidicount = 1
    for element in tree.findall(FIND_ANYWHERE_PREFIX + BIDI_PORT_TAG):
        # logger.debug log.debug(f"#FOUND PortGroup {element.tag} - {element.text} --- {element.attrib}")
        bidiport_id = element.attrib["id"]

        log.debug("nsi_parse_topology_sdp_xml_tree: DDSSTP", bidiport_id=bidiport_id)
        # Prepare new dict
        if (name_element := element.find(NAME_TAG)) is not None:
            name = name_element.text
        else:
            name = f"no name for {bidiport_id} in topology document"
        bidiports[bidiport_id] = {FASTUID_ID_KEY: bidicount, "name": name}  # id for fastui + name of bidiport
        bidicount += 1

    #    #logger.debug log.debug("#BIDIPORTS",bidiports)

    sdps = []

    # Find Relation hasInbountPort, which contains PortGroups that have the VLANS per unidirectional STP,
    # i.e., bidi + ":in". I consider those to be the same as the outbond ones.
    #
    # Also

    for element in tree.findall(FIND_ANYWHERE_PREFIX + RELATION_TAG):
        # log.debug(f"#FOUND2 Relation {element.tag} - {element.text} --- {element.attrib}")
        if element.attrib["type"] == RELATION_HAS_INBOUND_PORT_TYPE:

            # logger.debug log.debug("#hasINBOUNDPORT")
            # for inport in element.find(FIND_ANYWHERE_PREFIX+PORTGROUP_TAG):
            for inport in element.iterfind(FIND_ANYWHERE_PREFIX + PORTGROUP_TAG):

                # logger.debug log.debug("#INBOUND PORTGROUP",inport.attrib)

                # ISSUE: also matches PortGroup isAlias within

                if inport is not None:
                    inport_id = inport.attrib["id"]  # this is the bidiport_id + ":in"
                    bidiport_id = inport_id[: -len(INPORT_IN_POSTFIX)]

                    # logger.debug log.debug("INPORT",bidiport_id)

                    lg = inport.find(FIND_ANYWHERE_PREFIX + LABEL_GROUP_TAG)
                    # logger.debug log.debug("LABELGROUP",lg)
                    if lg is not None:
                        # logger.debug log.debug("#VLANS",lg.text)
                        vlanstr = lg.text

                    relalias = inport.find(FIND_ANYWHERE_PREFIX + RELATION_TAG)
                    log.debug("nsi_parse_topology_sdp_xml_tree: ALIAS", relalias=relalias)
                    if relalias is not None:
                        # log.debug("nsi_parse_topology_sdp_xml_tree: ALIAS attrib",relalias.attrib)
                        if relalias.attrib[RELATION_TYPE_ATTRIB] == RELATION_IS_ALIAS_TYPE:
                            # Found SDP
                            outport = relalias.find(FIND_ANYWHERE_PREFIX + PORTGROUP_TAG)
                            if outport is None:
                                log.debug("nsi_parse_topology_sdp_xml_tree: No portgroup in Relation isAlias")
                            else:
                                outport_id = outport.attrib[PORTGROUP_ID_ATTRIB]
                                log.debug(
                                    f"nsi_parse_topology_sdp_xml_tree: SDP found from {inport_id} to {outport_id}"
                                )
                                sdp = {"inport": inport_id, "outport": outport_id, "vlanranges": vlanstr}
                                sdps.append(sdp)

                    if inport is not None and lg is not None:
                        try:
                            bidi_dict = bidiports[bidiport_id]
                            bidi_dict["vlanranges"] = vlanstr
                        except KeyError:
                            traceback.print_exc()

    # Filter SDPs from bidiports to create pure STP list
    stps = {}
    for sbidiport_id in bidiports.keys():
        found = False
        for sdp in sdps:

            log.debug("SOADM:", sdp=sdp, bidiport=bidiports[sbidiport_id])
            inport_id = sdp["inport"]
            tbidiport_id = inport_id[: -len(INPORT_IN_POSTFIX)]
            if sbidiport_id == tbidiport_id:
                log.debug("Dropping SDP from STPs", sbidiport_id=sbidiport_id)
                found = True
        if not found:
            log.debug("Adding STP to STPs", sbidiport_id=sbidiport_id)
            stps[sbidiport_id] = bidiports[sbidiport_id]

    retdict = {}
    retdict["sdps"] = sdps
    retdict["stps"] = stps
    return retdict


#
# SOAP functions
#
def nsi_connections_query(request_url, callback_url_prefix, provider_nsa_id):
    """NSI QUERY
    Returns: See nsi_soap_parse_query_reply
    """
    log = logger.bind()

    try:
        correlation_uuid_py = generate_uuid()

        # RESTFUL: Do Not Store (TODO or for security)
        reply_to_url = callback_url_prefix + "/query-callback/?corruuid=" + str(correlation_uuid_py)

        query_xml = generate_query_summary_sync_xml(
            query_summary_sync_templstr, correlation_uuid_py, reply_to_url, provider_nsa_id
        )

        # TODO: send XML to Safnari
        log.debug("nsi_connections_query: QUERY XML", query_xml=query_xml)
        log.debug("nsi_connections_query: CALLING ORCH")
        soap_xml = nsi_util_post_soap(request_url, query_xml)
        reservations = nsi_soap_parse_query_reply(soap_xml)

        log.debug("nsi_connections_query: Got reply parsed", reservations=reservations)
        return reservations

    except:
        traceback.print_exc()


def nsi_reserve(
    request_url,
    expect_correlation_uuid_py: UUID,
    orch_reply_to_url: str,
    provider_nsa_id: str,
    epnamea: str,
    epvlana: int,
    epnamez: str,
    epvlanz: int,
    linkname: str,
    linkid: int,
    duration_td: timedelta,
):
    """NSI RESERVE(SOAP-template,)
    Normally, the nsi_ code can generate the correlationID. For testing I sometimes need to
    pass a given correlationId, hence the parameter.
    Returns: dict with ["correlationId":correlationId,"connectionId":connectionId] as strings
    """
    log = logger.bind()

    try:
        connection_descr = NSI_RESERVE_XML_CONNECTION_PREFIX + " " + epnamea + " to " + epnamez + " over " + linkname
        start_datetime_py = datetime.datetime.now(datetime.timezone.utc)
        end_datetime_py = start_datetime_py + duration_td
        source_stp_dict = {URN_STP_NAME: epnamea, URN_STP_VLAN: epvlana}
        dest_stp_dict = {URN_STP_NAME: epnamez, URN_STP_VLAN: epvlanz}
        reply_to_url = orch_reply_to_url

        reserve_xml = generate_reserve_xml(
            reserve_templstr,
            expect_correlation_uuid_py,
            reply_to_url,
            connection_descr,
            generate_uuid(),  # uPA allows for this param, Aggregator does not. Currently Not used
            start_datetime_py,
            end_datetime_py,
            source_stp_dict,
            dest_stp_dict,
            provider_nsa_id,
        )

        # Send XML to Aggregator
        # Wait here for HTTP reply synchronously, which must have given CorrelationId
        log.debug("RESERVE: Request XML", reserve_xml=reserve_xml)
        soap_xml = nsi_util_post_soap(request_url, reserve_xml)

        log.debug("RESERVE: GOT HTTP REPLY", soap_xml=soap_xml)
        retdict = nsi_soap_parse_reserve_reply(soap_xml)

        log.debug("RESERVE: Got connectionId", retdict=retdict)
        # TODO: do type checking inside nsi_soap_parse()
        got_correlation_uuid_py = UUID(retdict["correlationId"])
        if got_correlation_uuid_py != expect_correlation_uuid_py:
            raise Exception("correlationId received in reply does not match the one sent in request.")

        retdict["correlationId"] = str(got_correlation_uuid_py)
        return retdict

    except Exception as e:
        traceback.print_exc()
        retdict[S_FAULTSTRING_TAG] = str(e)
        return retdict


def nsi_reserve_commit(request_url, provider_nsa_id: str, connid_str):
    """NSI RESERVE_COMMIT(SOAP-template,)
    Returns: dict with ["correlationId":correlationId,"connectionId":connectionId] as strings
    """
    log = logger.bind()

    try:
        correlation_uuid_py = generate_uuid()

        # RESTFUL: Do Not Store (TODO or for security)
        # reply_to_url = callback_url_prefix+"/reserve-commit-callback/?corruuid="+str(correlation_uuid_py)+"&globresuuid="+str(global_reservation_uuid_py)+"&connid"+connid_str
        # I get an error from SuPA: Unexpected character \'=\' (code 61); expected a semi-colon after the reference for entity \'globresuuid\'\n
        reply_to_url = callback_url_prefix + "/reserve-commit-callback/"

        reserve_commit_xml = generate_reserve_commit_xml(
            reserve_commit_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id
        )

        log.debug("RESERVE-COMMIT: Request XML", reserve_commit_xml=reserve_commit_xml)

        # TODO: send XML to Safnari
        log.debug("RESERVE-COMMIT: CALLING ORCH")
        soap_xml = nsi_util_post_soap(request_url, reserve_commit_xml)

        log.debug("RESERVE-COMMIT: GOT HTTP REPLY", soap_xml=soap_xml)

        retdict = nsi_soap_parse_reserve_commit_reply(soap_xml)

        log.debug("RESERVE-COMMIT: Got correlationId", retdict=retdict)

        # TODO: verify correlationId are the same

        return retdict

    except:
        traceback.print_exc()


def nsi_provision(request_url, callback_url_prefix: str, provider_nsa_id: str, connid_str):
    """NSI PROVISION(SOAP-template,)
    Returns: dict with ["correlationId":correlationId,"connectionId":connectionId] as strings
    """
    log = logger.bind()

    try:
        correlation_uuid_py = generate_uuid()

        # RESTFUL: Do Not Store (TODO or for security)
        # reply_to_url = callback_url_prefix+"/reserve-commit-callback/?corruuid="+str(correlation_uuid_py)+"&globresuuid="+str(global_reservation_uuid_py)+"&connid"+connid_str
        # I get an error from SuPA: Unexpected character \'=\' (code 61); expected a semi-colon after the reference for entity \'globresuuid\'\n
        reply_to_url = callback_url_prefix + "/provision-callback/"

        provision_xml = generate_provision_xml(
            provision_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id
        )

        log.debug("PROVISION: Request XML", provision_xml=provision_xml)

        # TODO: send XML to Safnari
        log.debug("PROVISION: CALLING ORCH")
        soap_xml = nsi_util_post_soap(request_url, provision_xml)

        log.debug("PROVISION: GOT HTTP REPLY", soap_xml=soap_xml)

        retdict = nsi_soap_parse_provision_reply(soap_xml)

        log.debug("PROVISION: Got correlationId", retdict=retdict)
        # TODO: verify correlationId in reply are the same as in request

        return retdict

    except:
        traceback.print_exc()


def nsi_terminate(request_url, callback_url_prefix: str, provider_nsa_id: str, connid_str):
    """NSI TERMINATE(SOAP-template,)
    Returns: dict with ["correlationId":correlationId,"connectionId":connectionId] as strings
    """
    log = logger.bind()

    try:
        correlation_uuid_py = generate_uuid()

        # RESTFUL: Do Not Store (TODO or for security)
        # reply_to_url = callback_url_prefix+"/reserve-commit-callback/?corruuid="+str(correlation_uuid_py)+"&globresuuid="+str(global_reservation_uuid_py)+"&connid"+connid_str
        # I get an error from SuPA: Unexpected character \'=\' (code 61); expected a semi-colon after the reference for entity \'globresuuid\'\n
        reply_to_url = callback_url_prefix + "/terminate-callback/"

        terminate_xml = generate_terminate_xml(
            terminate_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id
        )

        log.debug("TERMINATE: Request XML", terminate_xml=terminate_xml)

        # TODO: send XML to Safnari
        log.debug("TERMINATE: CALLING ORCH")
        soap_xml = nsi_util_post_soap(request_url, terminate_xml)

        log.debug("TERMINATE: GOT HTTP REPLY", soap_xml=soap_xml)

        retdict = nsi_soap_parse_terminate_reply(soap_xml)

        log.debug(f"TERMINATE: Got fault {retdict[S_FAULTSTRING_TAG]} correlationId {retdict[S_CORRELATION_ID_TAG]}")

        # TODO: verify correlationId are the same

        return retdict

    except:
        traceback.print_exc()


def nsi_release(request_url, callback_url_prefix: str, provider_nsa_id: str, connid_str):
    """NSI RELEASE (SOAP-template,)
    Returns: dict with ["correlationId":correlationId,"connectionId":connectionId] as strings
    """
    log = logger.bind()

    try:
        correlation_uuid_py = generate_uuid()

        # RESTFUL: Do Not Store (TODO or for security)
        # reply_to_url = callback_url_prefix+"/reserve-commit-callback/?corruuid="+str(correlation_uuid_py)+"&globresuuid="+str(global_reservation_uuid_py)+"&connid"+connid_str
        # I get an error from SuPA: Unexpected character \'=\' (code 61); expected a semi-colon after the reference for entity \'globresuuid\'\n
        reply_to_url = callback_url_prefix + "/terminate-callback/"

        release_xml = generate_release_xml(
            release_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id
        )

        log.debug("RELEASE: Request XML", release_xml=release_xml)

        # TODO: send XML to Safnari
        log.debug("RELEASE: CALLING ORCH")
        soap_xml = nsi_util_post_soap(request_url, release_xml)

        log.debug("RELEASE: GOT HTTP REPLY", soap_xml=soap_xml)

        retdict = nsi_soap_parse_release_reply(soap_xml)

        log.debug(f"RELEASE: Got fault {retdict[S_FAULTSTRING_TAG]} correlationId {retdict[S_CORRELATION_ID_TAG]}")

        # TODO: verify correlationId are the same

        return retdict

    except:
        traceback.print_exc()


def nsi_reserve_timeout_ack(request_url, callback_url_prefix: str, provider_nsa_id: str, connid_str):
    """NSI RESERVE-TIMEOUT-ACK(SOAP-template,)
    Returns: dict with ["correlationId":correlationId,"connectionId":connectionId] as strings
    """
    log = logger.bind()

    try:
        correlation_uuid_py = generate_uuid()

        # RESTFUL: Do Not Store (TODO or for security)
        # reply_to_url = callback_url_prefix+"/reserve-commit-callback/?corruuid="+str(correlation_uuid_py)+"&globresuuid="+str(global_reservation_uuid_py)+"&connid"+connid_str
        # I get an error from SuPA: Unexpected character \'=\' (code 61); expected a semi-colon after the reference for entity \'globresuuid\'\n
        reply_to_url = callback_url_prefix + "/terminate-callback/"

        reserve_timeout_ack_xml = generate_reserve_timeout_ack_xml(
            reserve_timeout_ack_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id
        )

        log.debug("RESERVE_TIMEOUT_ACK: Request XML", reserve_timeout_ack_xml=reserve_timeout_ack_xml)

        # TODO: send XML to Safnari
        log.debug("RESERVE_TIMEOUT_ACK: CALLING ORCH")
        soap_xml = nsi_util_post_soap(request_url, reserve_timeout_ack_xml)

        log.debug("RESERVE_TIMEOUT_ACK: GOT HTTP REPLY", soap_xml=soap_xml)

        retdict = nsi_soap_parse_reserve_timeout_ack_reply(soap_xml)

        print(
            "RESERVE_TIMEOUT_ACK: Got fault ",
            retdict[S_FAULTSTRING_TAG],
            "correlationId",
            retdict[S_CORRELATION_ID_TAG],
        )

        # TODO: verify correlationId are the same

        return retdict

    except:
        traceback.print_exc()


def nsi_query_recursive(request_url, orch_reply_to_url: str, provider_nsa_id: str, connid_str):
    """NSI QUERY RECURSIVE(SOAP-template,)
    Returns: dict with ["correlationId":correlationId,"connectionId":connectionId] as strings
    """
    log = logger.bind()

    try:
        correlation_uuid_py = generate_uuid()

        # RESTFUL: Do Not Store (TODO or for security)
        # reply_to_url = callback_url_prefix+"/reserve-commit-callback/?corruuid="+str(correlation_uuid_py)+"&globresuuid="+str(global_reservation_uuid_py)+"&connid"+connid_str
        # I get an error from SuPA: Unexpected character \'=\' (code 61); expected a semi-colon after the reference for entity \'globresuuid\'\n
        reply_to_url = orch_reply_to_url

        query_recursive_xml = generate_query_recursive_xml(
            query_recursive_templstr, correlation_uuid_py, reply_to_url, connid_str, provider_nsa_id
        )

        log.debug("QUERY_RECURSIVE: Request XML", query_recursive_xml=query_recursive_xml)

        # TODO: send XML to Safnari
        log.debug("QUERY_RECURSIVE: CALLING ORCH")
        soap_xml = nsi_util_post_soap(request_url, query_recursive_xml)

        log.debug("QUERY_RECURSIVE: GOT HTTP REPLY", soap_xml=soap_xml)

        retdict = nsi_soap_parse_query_recursive_reply(soap_xml)

        log.debug(
            f"QUERY_RECURSIVE: Got fault {retdict[S_FAULTSTRING_TAG]} correlationId {retdict[S_CORRELATION_ID_TAG]}"
        )

        # TODO: verify correlationId are the same

        return retdict

    except:
        traceback.print_exc()


def nsi_soap_parse_callback(body):
    """Extracts correlationID from Aggregator async callback.
    @return UUID as UUID class
    """
    log = logger.bind()

    tree = nsi_util_parse_xml(body)
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CORRELATION_ID_TAG)
    if tag is not None:
        log.debug("CALLBACK: Found correlationId", tag=tag.text)
        correlation_urn = tag.text
        # Checks input format
        correlation_uuid = UUID(correlation_urn)
        return correlation_uuid
    log.debug("CALLBACK: Could not find correlationId", body=body)
    raise Exception("correlationId not found in callback")


def nsi_soap_parse_error_event(body):
    """Extracts connectionId and serviceException from Aggregator async errorEvent.
    @return UUID as UUID class
    """
    log = logger.bind()

    tree = nsi_util_parse_xml(body)
    element = tree.find(FIND_ANYWHERE_PREFIX + S_CONNECTION_ID_TAG)
    if element is not None:
        log.debug("CALLBACK: Found connectionId", element=element.text)
        connectionId = UUID(element.text)
        element = tree.find(FIND_ANYWHERE_PREFIX + S_SERVICE_EXCEPTION_TAG)
        if element is not None:
            log.debug("CALLBACK: Found serviceException")
            return connectionId, {element.tag: element.text for element in element.iter()}
    log.debug("CALLBACK: Could not find connectionId and/or serviceException in errorEvent", body=body)
    raise Exception("errorEvent not found in callback")


def content_type_is_valid_soap(content_type):
    """Returns True if HTTP Content-Type indicates SOAP"""
    ct = content_type.lower()
    return ct == "application/xml" or ct.startswith("text/xml")  # "text/xml;charset=utf-8" "text/xml; charset=UTF-8"


def nsi_util_post_soap(url, soapreqmsg):
    """Does HTTP POST of soapreqmsg to URL
    Returns: response.content, a SOAP reply
    """
    log = logger.bind()

    # headers = {'content-type': 'application/soap+xml'}
    headers = {"content-type": "text/xml"}
    body = soapreqmsg

    # 2024-11-08: SuPA moxy currently has self-signed certificate
    response = session.post(
        url,
        data=body,
        headers=headers,
        verify=(
            settings.CERTIFICATES_DIRECTORY
            if settings.VERIFY_REQUESTS and settings.CERTIFICATES_DIRECTORY
            else settings.VERIFY_REQUESTS
        ),
        cert=(settings.NSI_AURA_CERTIFICATE, settings.NSI_AURA_PRIVATE_KEY),
    )
    log.debug(response.status_code)
    if response.status_code != 200:
        response.raise_for_status()
    log.debug(f"#CONTENT TYPE# {response.headers['content-type']}")
    if content_type_is_valid_soap(response.headers["content-type"]):
        return response.content
    # log.debug(response.encoding)
    # log.debug(response.content)
    raise Exception(url + " did not return XML, but" + response.headers["content-type"])


#
# TODO: do type checking on UUIDs here? I'd say yes.
#


def nsi_soap_parse_query_reply(soap_xml):
    """Parses SOAP QUERY reply
    Returns: dictionary of Reservation tags, key ConnectionId, values interesting subset.
    """
    log = logger.bind()

    # Find all Reservation tags
    tree = None
    soap_file = BytesIO(soap_xml)
    tree = etree.parse(soap_file)

    #
    # Get all reservation tags and their content
    #

    reservations = {}  # indexed on connectionId

    rescount = 1
    for res in tree.findall(FIND_ANYWHERE_PREFIX + S_RESERVATION_TAG):
        # logger.debug log.debug(f"#FOUND Reservation {res.tag} - {res.text} --- {res.attrib}")

        reservation_dict = {FASTUID_ID_KEY: rescount}
        rescount += 1
        connection_uuidstr = None
        # TODO: convert to Python data types. Not to Model data-types, that should happen outside this function.
        # Not too much fastAPI dependencies
        for tag in S_QUERY_REPLY_TAGS:
            for element in res.findall(FIND_ANYWHERE_PREFIX + tag):
                if element.tag == S_RESERVATION_TAG:
                    continue  # code anomaly
                if element.tag == S_CONNECTION_ID_TAG:
                    connection_uuidstr = element.text
                elif element.tag == S_DESCRIPTION_TAG:
                    reservation_dict[tag] = element.text
                elif element.tag == S_STARTTIME_TAG:
                    reservation_dict[tag] = element.text
                elif element.tag == S_ENDTIME_TAG:
                    reservation_dict[tag] = element.text
                elif element.tag == S_SOURCE_STP_TAG:
                    reservation_dict[tag] = element.text
                elif element.tag == S_DEST_STP_TAG:
                    reservation_dict[tag] = element.text
                elif element.tag == S_REQUESTER_NSA_TAG:
                    reservation_dict[tag] = element.text
                elif element.tag == S_RESERVATION_STATE_TAG:
                    reservation_dict[tag] = element.text
                elif element.tag == S_LIFECYCLE_STATE_TAG:
                    reservation_dict[tag] = element.text
                elif element.tag == S_DATAPLANE_STATUS_TAG:
                    element2 = element.find(FIND_ANYWHERE_PREFIX + S_DATAPLANE_STATUS_ACTIVE_TAG)
                    reservation_dict[tag] = element2.text
        reservations[connection_uuidstr] = reservation_dict

    return reservations


def nsi_soap_parse_reserve_reply(soap_xml):
    """Parses SOAP RESERVE reply
    Returns: ConnectionId as string
    """
    log = logger.bind()

    # Parse XML
    tree = None
    soap_file = BytesIO(soap_xml)
    tree = etree.parse(soap_file)

    #
    # Get correlationId
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CORRELATION_ID_TAG)
    correlation_id_str = tag.text

    #
    # Get connectionId
    #
    # TODO: check for error / faultstring
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CONNECTION_ID_TAG)
    connection_id_str = tag.text

    tag = tree.find(FIND_ANYWHERE_PREFIX + S_FAULTSTRING_TAG)
    if tag is None:
        faultstring = None
    else:
        faultstring = tag.text

    log.debug("nsi_soap_parse_reserve_reply: Got error?", faultstring=faultstring)

    retdict = {}
    retdict[S_FAULTSTRING_TAG] = faultstring
    retdict[S_CORRELATION_ID_TAG] = correlation_id_str
    retdict[S_CONNECTION_ID_TAG] = connection_id_str
    return retdict


def nsi_soap_parse_reserve_commit_reply(soap_xml):
    return nsi_soap_parse_correlationid_reply(soap_xml)


def nsi_soap_parse_provision_reply(soap_xml):
    return nsi_soap_parse_correlationid_reply(soap_xml)


def nsi_soap_parse_terminate_reply(soap_xml):
    return nsi_soap_parse_correlationid_reply(soap_xml)


def nsi_soap_parse_release_reply(soap_xml):
    return nsi_soap_parse_terminate_reply(soap_xml)


def nsi_soap_parse_reserve_timeout_ack_reply(soap_xml):
    return nsi_soap_parse_terminate_reply(soap_xml)


def nsi_soap_parse_query_recursive_reply(soap_xml):
    return nsi_soap_parse_correlationid_reply(soap_xml)


def nsi_soap_parse_correlationid_reply(soap_xml):
    """Parses SOAP PROVISION reply
    Returns: dict with S_FAULTSTRING_TAG and S_CORRELATION_ID_TAG as keys, values string
    if S_FAULTSTRING_TAG is not None, there was a faulstring tag.
    """
    log = logger.bind()

    # Parse XML
    tree = None
    soap_file = BytesIO(soap_xml)
    tree = etree.parse(soap_file)

    #
    # Get correlationId
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CORRELATION_ID_TAG)
    correlation_id_str = tag.text

    tag = tree.find(FIND_ANYWHERE_PREFIX + S_FAULTSTRING_TAG)
    if tag is None:
        faultstring = None
    else:
        faultstring = tag.text

    log.debug("nsi_soap_parse_correlationid_reply: Got error?", faultstring=faultstring)

    retdict = {}
    retdict[S_FAULTSTRING_TAG] = faultstring
    retdict[S_CORRELATION_ID_TAG] = correlation_id_str
    return retdict


def nsi_soap_parse_reserve_callback(soap_xml):
    """Parses SOAP RESERVE async callback
    Returns: dictionary with relevant fields
    """
    log = logger.bind()

    # Parse XML
    tree = None
    soap_file = BytesIO(soap_xml)
    tree = etree.parse(soap_file)

    #
    # Get connectionId
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CONNECTION_ID_TAG)
    connection_id_str = tag.text

    #
    # Get correlationId
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CORRELATION_ID_TAG)
    correlation_id_str = tag.text

    #
    # Get state: reserveConfirmed, TODO: which others, cannot tell from State Diagram
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_RESERVE_CONFIRMED_TAG)
    callback_state_str = tag.tag

    # log.debug("nsi_soap_parse_reserve_callback: Finding", tag)
    # log.debug("nsi_soap_parse_reserve_callback: Finding", tree.find(FIND_ANYWHERE_PREFIX+"nsi_ctypes:reserveConfirmed"))
    # log.debug("nsi_soap_parse_reserve_callback: Finding", tree.find(FIND_ANYWHERE_PREFIX+"reserveConfirmed"))

    #
    # Get source STP
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_SOURCE_STP_TAG)
    source_stp_str = tag.text

    #
    # Get dest STP
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_SOURCE_STP_TAG)
    dest_stp_str = tag.text

    # Should not be a fault string, that should have been reported in the HTTP reply, not async
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_FAULTSTRING_TAG)
    if tag is None:
        faultstring = None
    else:
        faultstring = tag.text

    log.debug("nsi_soap_parse_reserve_callback: SOAP faultString:", faultstring=faultstring)

    retdict = {}
    retdict[S_FAULTSTRING_TAG] = faultstring
    retdict[S_CONNECTION_ID_TAG] = connection_id_str
    retdict[S_CORRELATION_ID_TAG] = correlation_id_str
    retdict[S_RESERVE_CONFIRMED_TAG] = callback_state_str
    retdict[S_SOURCE_STP_TAG] = source_stp_str
    retdict[S_DEST_STP_TAG] = dest_stp_str

    return retdict


def nsi_soap_parse_query_recursive_callback(soap_xml):
    """Parses SOAP QUERY-RECURSIVE async callback
    Returns: dictionary with relevant fields
    """
    log = logger.bind()

    # Parse XML
    tree = None
    soap_file = BytesIO(soap_xml)
    tree = etree.parse(soap_file)

    #
    # Get connectionId, not always present.
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CONNECTION_ID_TAG)
    if tag is None:
        connection_id_str = "Unknown ConnectionId"
    else:
        connection_id_str = tag.text

    #
    # Get correlationId
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CORRELATION_ID_TAG)
    correlation_id_str = tag.text

    #
    # Get state: reserveConfirmed, TODO: which others, cannot tell from State Diagram
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_QUERY_RECURSIVE_CONFIRMED_TAG)
    callback_state_str = tag.tag

    #
    # Find children of connection
    #
    children = {}
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CHILDREN_TAG)
    if tag is None:
        log.debug("nsi_soap_parse_query_recursive_callback: No children tag")
    else:
        for tag2 in tag.iterfind(FIND_ANYWHERE_PREFIX + S_CHILD_TAG):
            log.debug("nsi_soap_parse_query_recursive_callback: Found child", tag2=tag2)
            child_dict = {}
            tag3 = tag2.find(FIND_ANYWHERE_PREFIX + S_CONNECTION_ID_TAG)
            child_connectionid_str = tag3.text
            tag3 = tag2.find(FIND_ANYWHERE_PREFIX + S_SOURCE_STP_TAG)
            source_stp_str = tag3.text
            tag3 = tag2.find(FIND_ANYWHERE_PREFIX + S_DEST_STP_TAG)
            dest_stp_str = tag3.text
            child_dict[S_SOURCE_STP_TAG] = source_stp_str
            child_dict[S_DEST_STP_TAG] = dest_stp_str

            children[child_connectionid_str] = child_dict

    #
    # Get source STP
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_SOURCE_STP_TAG)
    if tag is None:
        source_stp_str = "Unknown source STP"
    else:
        source_stp_str = tag.text

    #
    # Get dest STP
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_SOURCE_STP_TAG)
    if tag is None:
        dest_stp_str = "Unknown dest STP"
    else:
        dest_stp_str = tag.text

    # Should not be a fault string, that should have been reported in the HTTP reply, not async
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_FAULTSTRING_TAG)
    if tag is None:
        faultstring = None
    else:
        faultstring = tag.text

    log.debug("nsi_soap_parse_query_recursive_callback: SOAP PARSE CALLBACK FOR CONNECTIONID:", faultstring=faultstring)

    retdict = {}
    retdict[S_FAULTSTRING_TAG] = faultstring
    retdict[S_CONNECTION_ID_TAG] = connection_id_str
    retdict[S_CORRELATION_ID_TAG] = correlation_id_str
    retdict[S_QUERY_RECURSIVE_CONFIRMED_TAG] = callback_state_str
    retdict[S_SOURCE_STP_TAG] = source_stp_str
    retdict[S_DEST_STP_TAG] = dest_stp_str
    retdict[S_CHILDREN_TAG] = children

    log.debug("nsi_soap_parse_query_recursive_callback: Found children", children=children)

    return retdict


# if __name__ == "__main__":

# nsi_comm_init("static")

# dds_documents_dict = nsi_get_dds_documents("https://dds.ana.dlp.surfnet.nl/dds/documents/")
# log.debug("FINAL DOCS", dds_documents_dict)
