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

import json

import structlog
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import utc

from amiss.agg import get_aggregator_reservations, temp_pull_reservations_from_agg, update_segments
from amiss.db import Session
from amiss.dds import (
    dds_proxy_json_to_sdps,
    dds_proxy_json_to_stps,
    get_dds_proxy_sdps,
    get_dds_proxy_stps,
    update_stps,
)
from amiss.model import SDP, STP
from amiss.settings import settings

# Advanced Python Scheduler
# scheduler = AsyncIOScheduler(event_loop=asyncio.get_running_loop(), timezone=utc)
scheduler = BackgroundScheduler(
    jobstores={"default": MemoryJobStore()},
    executors={"default": ThreadPoolExecutor(max_workers=10)},
    job_defaults={"coalesce": False, "max_instances": 1, "misfire_grace_time": None},
    timezone=utc,
)


logger = structlog.get_logger(__name__)


def nsi_poll_dds_job() -> None:
    """Poll the DDS proxy for STPs and SDPs and refresh the database.

    Wipes the STP and SDP tables first, then repopulates them from the DDS proxy.
    """
    url = settings.NSI_DDS_PROXY_URL
    log = logger.bind(url=str(url))
    log.warning("polling dds proxy")

    with Session.begin() as session:
        session.query(SDP).delete()
        session.query(STP).delete()

    stps_json = get_dds_proxy_stps(url)
    if stps_json is not None:
        update_stps(dds_proxy_json_to_stps(json.loads(stps_json)))
    sdps_json = get_dds_proxy_sdps(url)
    if sdps_json is not None:
        dds_proxy_json_to_sdps(json.loads(sdps_json))

def nsi_poll_agg_job() -> None:
    """Poll the Aggregator for reservations and persist their Segments to the database."""
    url = settings.NSI_AGG_PROXY_URL
    log = logger.bind(url=str(url))
    log.warning("polling agg proxy")

    jsondata = get_aggregator_reservations(url)
    if jsondata is None:
        # Error already logged
        return
    try:
        jsondict = json.loads(jsondata)
    except (json.JSONDecodeError, ValueError) as e:
        log.warning("cannot parse reservations JSON document", error=str(e))
        return
    if "reservations" not in jsondict:
        log.warning("no reservations in reservations JSON document")
        return

    temp_pull_reservations_from_agg(jsondict["reservations"])

    for resdict in jsondict["reservations"]:
        if "connectionId" in resdict and "segments" in resdict:
            update_segments(resdict["connectionId"], resdict["segments"])


def nsi_poll_sources() -> None:
    """Poll all upstream sources: the DDS proxy (STPs/SDPs) first, then the aggregator (reservations/segments).

    Order matters: the aggregator poll's temp_pull_reservations_from_agg resolves reservation STP URNs
    against the STP rows the DDS poll just refreshed.
    """
    log = logger.bind(url="about:sources")
    if settings.SEED_DUMMY_SEGMENTS_DATA:
        log.warning("operating on dummy data, not polling sources")
    else:
        nsi_poll_dds_job()
        nsi_poll_agg_job()
