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

from uuid import UUID, uuid4

import structlog
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import utc

from aura.db import Session
from aura.dds import TOPOLOGY_MIME_TYPE, get_dds_documents, topology_to_stps, update_sdps, update_stps
from aura.agg import segdicts_to_segments
from aura.fsm import ConnectionStateMachine
from aura.model import STP, Reservation
from aura.nsi import (
    nsi_send_provision,
    nsi_send_release,
    nsi_send_reserve,
    nsi_send_reserve_commit,
    nsi_send_terminate,
    nsi_xml_to_dict, nsi_util_get_json,
)
from aura.settings import settings

# Advanced Python Scheduler
# scheduler = AsyncIOScheduler(event_loop=asyncio.get_running_loop(), timezone=utc)
scheduler = BackgroundScheduler(
    jobstores={"default": MemoryJobStore()},
    executors={"default": ThreadPoolExecutor(max_workers=10)},
    job_defaults={"coalesce": False, "max_instances": 1, "misfire_grace_time": None},
    timezone=utc,
)


logger = structlog.get_logger(__name__)


def new_correlation_id_on_reservation(reservation_id: int) -> None:
    with Session.begin() as session:
        reservation = session.query(Reservation).filter(Reservation.id == reservation_id).one()  # type: ignore[arg-type]
        reservation.correlationId = uuid4()

def nsi_poll_dds_job() -> None:
    """Poll the DDS for topology documents and update STP and SDP."""
    documents = get_dds_documents(settings.NSI_DDS_URL)
    stps = [stp for xml in documents[TOPOLOGY_MIME_TYPE].values() for stp in topology_to_stps(nsi_xml_to_dict(xml))]
    update_stps(stps)
    update_sdps()

def nsi_poll_agg_job() -> None:
    """Poll the Aggregator for reservations and update Reservations and Segment data model."""
    queryparams = {"details":"full"}
    url = settings.NSI_AGG_PROXY_URL
    jsondata = nsi_util_get_json(url,queryparams)
    if jsondata is None:
        # Error already logged
        return
    try:
        jsondict = json.loads(jsondata)
    except Error as e:
        log.warning("cannot parse reservations JSON document", url=str(url), error=str(e))
        return None
    if "reservations" not in jsondict:
        log.warning("No reservations in reservations JSON document", url=str(url))
        return None

    # Update Reservations
    for resdict in jsondict["reservations"]:
        # ARNOTODO
        # Update reservations DB
        if "connectionId" in resdict and "segments" in resdict:
            # Update Segments DB
            segments = segdicts_to_segments(resdict["connectionId"],resdict["segments"])



def nsi_send_reserve_job(reservation_id: int) -> None:
    new_correlation_id_on_reservation(reservation_id)
    with Session() as session:
        reservation = session.query(Reservation).filter(Reservation.id == reservation_id).one()  # type: ignore[arg-type]
        source_stp = session.query(STP).filter(STP.id == reservation.sourceStpId).one()  # type: ignore[arg-type]  # TODO: replace with relation
        dest_stp = session.query(STP).filter(STP.id == reservation.destStpId).one()  # type: ignore[arg-type]  # TODO: replace with relation
    try:
        retdict = nsi_send_reserve(reservation, source_stp, dest_stp)  # TODO: need error handling post soap failure
    except OSError as e:
        log = logger.bind(reservationId=reservation.id, globalReservationId=str(reservation.globalReservationId))
        log.warning(str(e))
        with Session.begin() as session:
            reservation = session.query(Reservation).filter(Reservation.id == reservation_id).one()  # type: ignore[arg-type]
            csm = ConnectionStateMachine(reservation)
            csm.connection_error()
    else:
        with Session.begin() as session:
            reservation = session.query(Reservation).filter(Reservation.id == reservation_id).one()  # type: ignore[arg-type]
            reservation.connectionId = UUID(retdict["connectionId"])  # TODO: make nsi_comm return a UUID


def nsi_send_reserve_commit_job(reservation_id: int) -> None:
    new_correlation_id_on_reservation(reservation_id)
    with Session() as session:
        reservation = session.query(Reservation).filter(Reservation.id == reservation_id).one()  # type: ignore[arg-type]
    nsi_send_reserve_commit(reservation)  # TODO: need error handling on failed post soap


def nsi_send_provision_job(reservation_id: int) -> None:
    new_correlation_id_on_reservation(reservation_id)
    with Session() as session:
        reservation = session.query(Reservation).filter(Reservation.id == reservation_id).one()  # type: ignore[arg-type]
    nsi_send_provision(reservation)  # TODO: need error handling on failed post soap


def nsi_send_terminate_job(reservation_id: int) -> None:
    new_correlation_id_on_reservation(reservation_id)
    with Session() as session:
        reservation = session.query(Reservation).filter(Reservation.id == reservation_id).one()  # type: ignore[arg-type]
    log = logger.bind(
        reservationId=reservation.id,
        correlationId=str(reservation.correlationId),
        connectionId=str(reservation.connectionId),
    )
    log.info("send terminate to nsi provider")
    reply_dict = nsi_send_terminate(reservation)
    if "Fault" in reply_dict["Body"]:
        se = reply_dict["Body"]["Fault"]["detail"]["serviceException"]
        log.warning(f"send terminate failed: {se['text']}", nsaId=se["nsaId"], errorId=se["errorId"], text=se["text"])
        # TODO: transition to error state (that needs to be defined)
    else:
        log.info("terminate successfully sent")


def nsi_send_release_job(reservation_id: int) -> None:
    new_correlation_id_on_reservation(reservation_id)
    with Session() as session:
        reservation = session.query(Reservation).filter(Reservation.id == reservation_id).one()  # type: ignore[arg-type]
    log = logger.bind(
        reservationId=reservation.id,
        correlationId=str(reservation.correlationId),
        connectionId=str(reservation.connectionId),
    )
    log.info("send release to nsi provider")
    reply_dict = nsi_send_release(reservation)
    if "Fault" in reply_dict["Body"]:
        se = reply_dict["Body"]["Fault"]["detail"]["serviceException"]
        log.warning(f"send release failed: {se['text']}", nsaId=se["nsaId"], errorId=se["errorId"], text=se["text"])
        # TODO: transition to error state (that needs to be defined)
    else:
        log.info("send release successful")
