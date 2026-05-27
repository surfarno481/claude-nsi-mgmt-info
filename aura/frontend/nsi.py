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

import structlog
from fastapi import APIRouter, Request, Response
from statemachine.exceptions import TransitionNotAllowed

from aura.fsm import ConnectionStateMachine
from aura.job import nsi_send_reserve_commit_job, scheduler
from aura.model import Reservation
from aura.nsi import acknowledgement_template, generate_acknowledgement_xml, nsi_xml_to_dict
from aura.settings import settings

router = APIRouter()

logger = structlog.get_logger(__name__)


def soap_action(request: Request, action: str) -> bool:
    """Check if the given action matches the soap action header on the request."""
    return request.headers["soapaction"] == action


@router.post("/callback/")
async def nsi_callback(request: Request) -> Response:
    """Receive and process NSI async callback."""
    from aura.db import Session

    body = nsi_xml_to_dict(await request.body())
    with Session.begin() as session:
        try:
            # TODO: add PassedEndTime
            if soap_action(request, '"http://schemas.ogf.org/nsi/2013/12/connection/service/errorEvent"'):
                connectionId = body["Body"]["errorEvent"]["connectionId"]
                reservation = session.query(Reservation).filter(Reservation.connectionId == connectionId).one()
            elif soap_action(request, '"http://schemas.ogf.org/nsi/2013/12/connection/service/dataPlaneStateChange"'):
                connectionId = body["Body"]["dataPlaneStateChange"]["connectionId"]
                reservation = session.query(Reservation).filter(Reservation.connectionId == connectionId).one()
            elif soap_action(request, '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveTimeout"'):
                connectionId = body["Body"]["reserveTimeout"]["connectionId"]
                reservation = session.query(Reservation).filter(Reservation.connectionId == connectionId).one()
            else:
                correlationId = body["Header"]["nsiHeader"]["correlationId"]
                reservation = session.query(Reservation).filter(Reservation.correlationId == correlationId).one()
            log = logger.bind(
                reservationId=reservation.id,
                correlationId=str(reservation.correlationId),
                connectionId=str(reservation.connectionId),
            )
            # update connection state machine
            csm = ConnectionStateMachine(reservation)
            match request.headers["soapaction"]:
                case '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveFailed"':
                    se = body["Body"]["reserveFailed"]["serviceException"]
                    text = se["childException"]["text"] if "childException" in se else se["text"]
                    log.warning(f"reserve failed from nsi provider: {text}")
                    csm.nsi_receive_reserve_failed()
                case '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveTimeout"':
                    log.warning("reserve timeout from nsi provider")
                    csm.nsi_receive_reserve_timeout()
                case '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveConfirmed"':
                    log.info("reserve confirmed from nsi provider")
                    csm.nsi_receive_reserve_confirmed()
                    csm.nsi_send_reserve_commit()  # TODO: decide if we want to auto commit or not
                # case '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveAbortConfirmed"':
                #     log.info("reserve abort confirmed from nsi provider")
                #     csm.nsi_receive_reserve_abort_confirmed()  # TODO: decide if we want to abort a modify or not
                case '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveCommitConfirmed"':
                    log.info("reserve commit confirmed from nsi provider")
                    csm.nsi_receive_reserve_commit_confirmed()
                case '"http://schemas.ogf.org/nsi/2013/12/connection/service/provisionConfirmed"':
                    log.info("provision confirmed from nsi provider")
                    csm.nsi_receive_provision_confirmed()
                case '"http://schemas.ogf.org/nsi/2013/12/connection/service/releaseConfirmed"':
                    log.info("release confirmed from nsi provider")
                    csm.nsi_receive_release_confirmed()
                case '"http://schemas.ogf.org/nsi/2013/12/connection/service/terminateConfirmed"':
                    log.info("terminate confirmed from nsi provider")
                    csm.nsi_receive_terminate_confirmed()
                case '"http://schemas.ogf.org/nsi/2013/12/connection/service/dataPlaneStateChange"':
                    active = body["Body"]["dataPlaneStateChange"]["dataPlaneStatus"]["active"]
                    if active == "true":
                        log.info("data plane state change up from nsi provider", active=active)
                        csm.nsi_receive_data_plane_up()
                    else:
                        log.info("data plane state change down from nsi provider", active=active)
                        csm.nsi_receive_data_plane_down()
                case '"http://schemas.ogf.org/nsi/2013/12/connection/service/errorEvent"':
                    text = body["Body"]["errorEvent"]["serviceException"]["text"]
                    log.warning(f"error event from nsi provider: {text}", text=text)
                    csm.nsi_receive_error_event()
                case _:
                    log.error("no matching soap action in message from nsi provider")
            reservation_id = reservation.id
        except TransitionNotAllowed as e:
            log.warning(str(e))
    # start job that corresponds with above state transition # TODO decide if we want to auto commit/provision or not
    match request.headers["soapaction"]:
        case '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveConfirmed"':
            scheduler.add_job(nsi_send_reserve_commit_job, args=[reservation_id])
        # case '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveCommitConfirmed"':
        #     scheduler.add_job(nsi_send_provision_job, args=[reservation_id])
        # case '"http://schemas.ogf.org/nsi/2013/12/connection/service/reserveAbortConfirmed"':
        #     scheduler.add_job(nsi_send_reserve_commit_job(), args=[reservation_id])

    nsi_acknowledgement = generate_acknowledgement_xml(
        acknowledgement_template, body["Header"]["nsiHeader"]["correlationId"], settings.NSI_PROVIDER_ID
    )
    return Response(content=nsi_acknowledgement, media_type="application/xml")
