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

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import requests
import requests.exceptions
import structlog
from lxml import etree
from pydantic import HttpUrl
from urllib3.util.retry import Retry

from aura.model import STP, Reservation
from aura.settings import settings

logger = structlog.get_logger(__name__)

#
# Module-only variables
#
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
# Metadata
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
# S_CONNECTION_ID_TAG='connectionId'

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


def generate_uuid() -> str:
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

# Templates
#
# RESERVE
reserve_template_path = settings.STATIC_DIRECTORY / NSI_RESERVE_TEMPLATE_XMLFILE

# Read Reserve template code
with reserve_template_path.open() as reserve_template_file:
    reserve_template = reserve_template_file.read()

# RESERVE-COMMIT
reserve_commit_template_path = settings.STATIC_DIRECTORY / NSI_RESERVE_COMMIT_TEMPLATE_XMLFILE

# Read Reserve Commit template code
with reserve_commit_template_path.open() as reserve_commit_template_file:
    reserve_commit_template = reserve_commit_template_file.read()

# RESERVE-ABORT
reserve_abort_template_path = settings.STATIC_DIRECTORY / NSI_RESERVE_ABORT_TEMPLATE_XMLFILE

# Read Reserve Abort template code
with reserve_abort_template_path.open() as reserve_abort_template_file:
    reserve_abort_template = reserve_abort_template_file.read()

# PROVISION
provision_template_path = settings.STATIC_DIRECTORY / NSI_PROVISION_TEMPLATE_XMLFILE

# Read Reserve template code
with provision_template_path.open() as provision_template_file:
    provision_template = provision_template_file.read()

# QUERY SUMMARY SYNC
query_summary_sync_template_path = settings.STATIC_DIRECTORY / NSI_QUERY_SUMMARY_SYNC_TEMPLATE_XMLFILE

# Read Reserve template code
with query_summary_sync_template_path.open() as query_summary_sync_template_file:
    query_summary_sync_template = query_summary_sync_template_file.read()

# QUERY RECURSIVE to get path details
query_recursive_template_path = settings.STATIC_DIRECTORY / NSI_QUERY_RECURSIVE_TEMPLATE_XMLFILE

# Read RESERVE_TIMEOUT_ACK template code
with query_recursive_template_path.open() as query_recursive_template_file:
    query_recursive_template = query_recursive_template_file.read()

# TERMINATE
terminate_template_path = settings.STATIC_DIRECTORY / NSI_TERMINATE_TEMPLATE_XMLFILE

# Read TERMINATE template code
with terminate_template_path.open() as terminate_template_file:
    terminate_template = terminate_template_file.read()

# RELEASE
release_template_path = settings.STATIC_DIRECTORY / NSI_RELEASE_TEMPLATE_XMLFILE

# Read RELEASE template code
with release_template_path.open() as release_template_file:
    release_template = release_template_file.read()

# RESERVE_TIMEOUT_ACK
reserve_timeout_ack_template_path = settings.STATIC_DIRECTORY / NSI_RESERVE_TIMEOUT_ACK_TEMPLATE_XMLFILE

# Read RESERVE_TIMEOUT_ACK template code
with reserve_timeout_ack_template_path.open() as reserve_timeout_ack_template_file:
    reserve_timeout_ack_template = reserve_timeout_ack_template_file.read()

# ACKNOWLEDGEMENT
acknowledgement_template_path = settings.STATIC_DIRECTORY / NSI_ACKNOWLEDGEMENT_TEMPLATE_XMLFILE

# Read ACKNOWLEDGEMENT template code
with acknowledgement_template_path.open() as acknowledgement_template_file:
    acknowledgement_template = acknowledgement_template_file.read()


def generate_reserve_xml(
    message_template: str,
    correlation_uuid_py: UUID,
    reply_to_url: str,
    connection_descr: str,
    global_reservation_uuid_py: UUID,
    start_datetime_py: datetime,
    end_datetime_py: datetime,
    source_stp: str,
    dest_stp: str,
    provider_nsa_id: str,
) -> bytes:
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)
    global_reservation_urn = global_reservation_uuid_py.urn
    start_time_str = start_datetime_py.isoformat()
    end_time_str = end_datetime_py.isoformat()

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#REPLY-TO-URL#": reply_to_url,
        "#CONNECTION-DESCRIPTION#": connection_descr,
        "#GLOBAL-RESERVATION-ID#": global_reservation_urn,
        "#CONNECTION-START-TIME#": start_time_str,
        "#CONNECTION-END-TIME#": end_time_str,
        "#SOURCE-STP#": source_stp,
        "#DEST-STP#": dest_stp,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in message_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml.encode()


def generate_reserve_commit_xml(
    message_template: str, correlation_uuid_py: UUID, reply_to_url: str, connid_str: str, provider_nsa_id: str
) -> bytes:
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#REPLY-TO-URL#": reply_to_url,
        "#CONNECTION-ID#": connid_str,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in reserve_commit_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml.encode()


def generate_reserve_abort_xml(
    message_template: str, correlation_uuid_py: UUID, reply_to_url: str, connid_str: str, provider_nsa_id: str
) -> bytes:
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#REPLY-TO-URL#": reply_to_url,
        "#CONNECTION-ID#": connid_str,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in reserve_commit_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml.encode()


def generate_provision_xml(
    message_template: str, correlation_uuid_py: UUID, reply_to_url: str, connid_str: str, provider_nsa_id: str
) -> bytes:
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#REPLY-TO-URL#": reply_to_url,
        "#CONNECTION-ID#": connid_str,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in provision_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml.encode()


def generate_terminate_xml(
    message_template: str, correlation_uuid_py: UUID, reply_to_url: str, connid_str: str, provider_nsa_id: str
) -> bytes:
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#REPLY-TO-URL#": reply_to_url,
        "#CONNECTION-ID#": connid_str,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in terminate_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml.encode()


def generate_release_xml(
    message_template: str, correlation_uuid_py: UUID, reply_to_url: str, connid_str: str, provider_nsa_id: str
) -> bytes:
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#REPLY-TO-URL#": reply_to_url,
        "#CONNECTION-ID#": connid_str,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in terminate_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml.encode()


def generate_reserve_timeout_ack_xml(
    message_template: str, correlation_uuid_py: UUID, reply_to_url: str, connid_str: str, provider_nsa_id: str
) -> bytes:
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#REPLY-TO-URL#": reply_to_url,
        "#CONNECTION-ID#": connid_str,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in terminate_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml.encode()


def generate_acknowledgement_xml(message_template: str, correlation_uuid_py: UUID, provider_nsa_id: str) -> bytes:
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in acknowledgement_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml.encode()


def generate_query_summary_sync_xml(
    message_template: str, correlation_uuid_py: UUID, connid_str: str, provider_nsa_id: str
) -> bytes:
    # Generate values
    log = logger.bind()

    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#CONNECTION-ID#": connid_str,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in query_summary_sync_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    log.debug("QUERY_XML", message_xml=message_xml)
    return message_xml.encode()


def generate_query_recursive_xml(
    message_template: str, correlation_uuid_py: UUID, reply_to_url: str, connid_str: str, provider_nsa_id: str
) -> bytes:
    # Generate values
    correlation_urn = URN_UUID_PREFIX + str(correlation_uuid_py)

    message_dict = {
        "#CORRELATION-ID#": correlation_urn,
        "#REPLY-TO-URL#": reply_to_url,
        "#CONNECTION-ID#": connid_str,
        "#PROVIDER-NSA-ID#": provider_nsa_id,
    }

    message_xml = message_template
    for message_key in terminate_keys:
        message_xml = message_xml.replace(message_key, message_dict[message_key])

    return message_xml.encode()


#
# Library
#

requests_session_adapter = requests.adapters.HTTPAdapter(max_retries=Retry(connect=3, backoff_factor=0.1))
session = requests.Session()
session.mount("http://", requests_session_adapter)
session.mount("https://", requests_session_adapter)


def nsi_util_get_xml(url: HttpUrl) -> bytes | None:
    log = logger.bind()

    # throws Exception to higher layer for display to user
    log.debug("SENDING HTTP REQUEST FOR XML", url=str(url))
    # 2024-11-08: SuPA moxy currently has self-signed certificate
    try:
        r = session.get(
            str(url),
            verify=settings.verify,
            cert=(str(settings.NSI_AURA_CERTIFICATE), str(settings.NSI_AURA_PRIVATE_KEY)),
        )
    except requests.exceptions.ConnectionError as e:
        log.warning("cannot get XML document", url=str(url), error=str(e))
        return None
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

    if r.status_code != 200:
        log.warning(f"{url} returned {r.status_code} with message {r.reason}")
        return None
    if (content_type := r.headers["content-type"].lower()) != "application/xml":
        log.warning(f"{url} did not return application/xml but {content_type}")
        return None
    return r.content


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


def nsi_util_element_to_dict(node: Any, attributes: bool = True) -> dict[str, Any]:
    """Convert a lxml.etree node tree into a dict."""
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
                value = datetime.fromisoformat(element.text)  # type: ignore[assignment]
            else:
                value = element.text
        else:
            value = nsi_util_element_to_dict(element)  # type: ignore[assignment]
        # Create a list of values for multiple identical keys
        if key in result:
            if type(result[key]) is list:
                result[key].append(value)
            else:
                result[key] = [result[key], value]
        else:
            result[key] = value
    return result


def nsi_xml_to_dict(xml: bytes) -> dict[Any, Any]:
    """Convert XML string to dict."""
    return nsi_util_element_to_dict(etree.fromstring(xml))


#
# SOAP functions
#
def content_type_is_valid_soap(content_type: str) -> bool:
    """Validate that HTTP Content-Type indicates SOAP."""
    ct = content_type.lower()
    return ct == "application/xml" or ct.startswith("text/xml")  # "text/xml;charset=utf-8" "text/xml; charset=UTF-8"


def nsi_util_post_soap(url: HttpUrl, soapreqmsg: bytes) -> bytes:
    """Execute a HTTP POST of the supplied soapreqmsg to URL.

    Returns: response.content, a SOAP reply.
    """
    log = logger.bind()

    # headers = {'content-type': 'application/soap+xml'}
    headers = {"content-type": "text/xml"}
    body = soapreqmsg

    # 2024-11-08: SuPA moxy currently has self-signed certificate
    try:
        response = session.post(
            str(url),
            data=body,
            headers=headers,
            verify=settings.verify,
            cert=(str(settings.NSI_AURA_CERTIFICATE), str(settings.NSI_AURA_PRIVATE_KEY)),
        )
    except requests.exceptions.ConnectionError as e:
        log.warning("cannot get XML document", url=str(url), error=str(e))
        raise e
    log.debug(response.status_code)
    if response.status_code != 200:
        response.raise_for_status()
    log.debug(f"#CONTENT TYPE# {response.headers['content-type']}")
    if content_type_is_valid_soap(response.headers["content-type"]):
        return response.content
    # log.debug(response.encoding)
    # log.debug(response.content)
    raise Exception(str(url) + " did not return XML, but" + response.headers["content-type"])


def nsi_soap_parse_reserve_reply(soap_xml: bytes) -> dict[str, Any]:
    """Parse SOAP RESERVE reply.

    Returns: ConnectionId as string.
    """
    log = logger.bind()

    # Parse XML
    tree = etree.fromstring(soap_xml)

    #
    # Get correlationId
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CORRELATION_ID_TAG)
    correlation_id_str = tag.text  # type: ignore[union-attr]

    #
    # Get connectionId
    #
    # TODO: check for error / faultstring
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CONNECTION_ID_TAG)
    connection_id_str = tag.text  # type: ignore[union-attr]

    tag = tree.find(FIND_ANYWHERE_PREFIX + S_FAULTSTRING_TAG)
    if tag is None:
        faultstring = None
    else:
        faultstring = tag.text

    log.debug("nsi_soap_parse_reserve_reply: Got error?", faultstring=faultstring)

    return {
        S_FAULTSTRING_TAG: faultstring,
        S_CORRELATION_ID_TAG: correlation_id_str,
        S_CONNECTION_ID_TAG: connection_id_str,
    }


def nsi_soap_parse_reserve_commit_reply(soap_xml: bytes) -> dict[str, Any]:
    return nsi_soap_parse_correlationid_reply(soap_xml)


def nsi_soap_parse_provision_reply(soap_xml: bytes) -> dict[str, Any]:
    return nsi_soap_parse_correlationid_reply(soap_xml)


def nsi_soap_parse_terminate_reply(soap_xml: bytes) -> dict[str, Any]:
    return nsi_soap_parse_correlationid_reply(soap_xml)


def nsi_soap_parse_release_reply(soap_xml: bytes) -> dict[str, Any]:
    return nsi_soap_parse_terminate_reply(soap_xml)


def nsi_soap_parse_reserve_timeout_ack_reply(soap_xml: bytes) -> dict[str, Any]:
    return nsi_soap_parse_terminate_reply(soap_xml)


def nsi_soap_parse_query_recursive_reply(soap_xml: bytes) -> dict[str, Any]:
    return nsi_soap_parse_correlationid_reply(soap_xml)


def nsi_soap_parse_correlationid_reply(soap_xml: bytes) -> dict[str, Any]:
    """Parse SOAP PROVISION reply.

    Returns: dict with S_FAULTSTRING_TAG and S_CORRELATION_ID_TAG as keys, values string
    if S_FAULTSTRING_TAG is not None, there was a faulstring tag.
    """
    log = logger.bind()

    # Parse XML
    tree = etree.fromstring(soap_xml)

    #
    # Get correlationId
    #
    tag = tree.find(FIND_ANYWHERE_PREFIX + S_CORRELATION_ID_TAG)
    correlation_id_str = tag.text  # type: ignore[union-attr]

    tag = tree.find(FIND_ANYWHERE_PREFIX + S_FAULTSTRING_TAG)
    if tag is None:
        faultstring = None
    else:
        faultstring = tag.text

    log.debug("nsi_soap_parse_correlationid_reply: Got error?", faultstring=faultstring)

    return {
        S_FAULTSTRING_TAG: faultstring,
        S_CORRELATION_ID_TAG: correlation_id_str,
    }


#
#
#


def nsi_send_reserve(reservation: Reservation, source_stp: STP, dest_stp: STP) -> dict[str, str]:
    log = logger.bind(
        reservationId=reservation.id,
        globalReservationId=str(reservation.globalReservationId),
        correlationId=str(reservation.correlationId),
    )
    log.info("send reserve to nsi provider")
    reserve_xml = generate_reserve_xml(
        reserve_template,
        reservation.correlationId,
        str(settings.NSA_BASE_URL) + "api/nsi/callback/",
        reservation.description,
        reservation.globalReservationId,
        reservation.startTime.replace(tzinfo=timezone.utc) if reservation.startTime else datetime.now(timezone.utc),
        # start time, TODO: proper timezone handling
        (
            reservation.endTime.replace(tzinfo=timezone.utc)
            if reservation.endTime
            else datetime.now(timezone.utc) + timedelta(weeks=1040)
        ),  # end time
        f"{source_stp.urn_base}?vlan={reservation.sourceVlan}",
        f"{dest_stp.urn_base}?vlan={reservation.destVlan}",
        settings.NSI_PROVIDER_ID,
    )
    soap_xml = nsi_util_post_soap(settings.NSI_PROVIDER_URL, reserve_xml)
    retdict = nsi_soap_parse_reserve_reply(soap_xml)  # TODO: need error handling post soap failure
    log.info("reserve successfully sent", connectionId=str(retdict["connectionId"]))
    return retdict


def nsi_send_reserve_commit(reservation: Reservation) -> dict[str, str]:
    log = logger.bind(
        reservationId=reservation.id,
        correlationId=str(reservation.correlationId),
        connectionId=str(reservation.connectionId),
    )
    log.info("send reserve commit to nsi provider")
    soap_xml = generate_reserve_commit_xml(
        reserve_commit_template,
        reservation.correlationId,
        str(settings.NSA_BASE_URL) + "api/nsi/callback/",
        str(reservation.connectionId),
        settings.NSI_PROVIDER_ID,
    )
    soap_xml = nsi_util_post_soap(settings.NSI_PROVIDER_URL, soap_xml)
    retdict = nsi_soap_parse_reserve_commit_reply(soap_xml)  # TODO: need error handling on failed post soap
    log.info("reserve commit successful sent")
    return retdict


def nsi_send_provision(reservation: Reservation) -> dict[str, str]:
    log = logger.bind(
        reservationId=reservation.id,
        correlationId=str(reservation.correlationId),
        connectionId=str(reservation.connectionId),
    )
    log.info("send provision to nsi provider")
    soap_xml = generate_provision_xml(
        provision_template,
        reservation.correlationId,
        str(settings.NSA_BASE_URL) + "api/nsi/callback/",
        str(reservation.connectionId),
        settings.NSI_PROVIDER_ID,
    )
    soap_xml = nsi_util_post_soap(settings.NSI_PROVIDER_URL, soap_xml)
    retdict = nsi_soap_parse_provision_reply(soap_xml)  # TODO: need error handling on failed post soap
    log.info("provision successful sent")
    return retdict


def nsi_send_reserve_abort(reservation: Reservation) -> dict[str, Any]:
    soap_xml = generate_reserve_abort_xml(
        reserve_abort_template,
        reservation.correlationId,
        str(settings.NSA_BASE_URL) + "api/nsi/callback/",
        str(reservation.connectionId),
        settings.NSI_PROVIDER_ID,
    )
    soap_xml = nsi_util_post_soap(settings.NSI_PROVIDER_URL, soap_xml)
    return nsi_xml_to_dict(soap_xml)


def nsi_send_release(reservation: Reservation) -> dict[str, Any]:
    soap_xml = generate_release_xml(
        release_template,
        reservation.correlationId,
        str(settings.NSA_BASE_URL) + "api/nsi/callback/",
        str(reservation.connectionId),
        settings.NSI_PROVIDER_ID,
    )
    soap_xml = nsi_util_post_soap(settings.NSI_PROVIDER_URL, soap_xml)
    return nsi_xml_to_dict(soap_xml)


def nsi_send_terminate(reservation: Reservation) -> dict[str, Any]:
    soap_xml = generate_terminate_xml(
        terminate_template,
        reservation.correlationId,
        str(settings.NSA_BASE_URL) + "api/nsi/callback/",
        str(reservation.connectionId),
        settings.NSI_PROVIDER_ID,
    )
    soap_xml = nsi_util_post_soap(settings.NSI_PROVIDER_URL, soap_xml)
    return nsi_xml_to_dict(soap_xml)


def nsi_send_query_summary_sync(reservation: Reservation) -> dict[str, Any]:
    """Send NSI query SOAP/XML message to NSI provider for given reservation.

    Every NSI request needs a unique correlation id,
    will set a new correlationId on message her but not store it on the reservation,
    thus not interfering with any currently outstanding other NSI request,
    and we do not expect a async reply on this sync request anyway.
    """
    soap_xml = generate_query_summary_sync_xml(
        query_summary_sync_template,
        uuid4(),
        str(reservation.connectionId),
        settings.NSI_PROVIDER_ID,
    )
    soap_xml = nsi_util_post_soap(settings.NSI_PROVIDER_URL, soap_xml)
    return nsi_xml_to_dict(soap_xml)
