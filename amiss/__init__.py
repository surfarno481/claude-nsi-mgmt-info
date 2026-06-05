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

from datetime import UTC, datetime, timedelta

from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastui import prebuilt_html
from starlette.responses import HTMLResponse, PlainTextResponse

from amiss.frontend.healthcheck import router as healthcheck_router
from amiss.frontend.home import router as home_router
from amiss.frontend.nsi import router as nsi_router
from amiss.frontend.reservations import router as reservations_router
from amiss.frontend.sdp import router as sdp_router
from amiss.frontend.stp import router as stp_router
from amiss.frontend.spectrum import router as spectrum_router
from amiss.job import nsi_poll_dds_job, scheduler
from amiss.log import init as log_init
from amiss.settings import settings

#
# logging
#
log_init()

#
# scheduler
#
scheduler.start()
# run poll job every minute starting on the next whole minute and do not let jobs queue up
scheduler.add_job(
    nsi_poll_dds_job,
    trigger=IntervalTrigger(
        minutes=1, start_date=datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1)
    ),
    coalesce=True,
)

#
# application
#
app = FastAPI()

# make sure the folder named 'static' exists in the project,
# and put the css and js files inside a subfolder called 'assets'
app.mount("/static", StaticFiles(directory=settings.STATIC_DIRECTORY), name="static")

# include routes
app.include_router(healthcheck_router)
app.include_router(reservations_router, prefix="/api/reservations")
app.include_router(stp_router, prefix="/api/stp")
app.include_router(sdp_router, prefix="/api/sdp")

app.include_router(spectrum_router, prefix="/api/spectrum")
app.include_router(nsi_router, prefix="/api/nsi")
app.include_router(home_router, prefix="/api")


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt() -> str:
    return "User-agent: *\nAllow: /"


@app.get("/favicon.ico", status_code=404, response_class=PlainTextResponse)
async def favicon_ico() -> str:
    return "page not found"


@app.get("/{path:path}")
async def html_landing() -> HTMLResponse:
    kwargs: dict = {"title": settings.SITE_TITLE}
    if settings.ROOT_PATH:
        kwargs["api_root_url"] = f"{settings.ROOT_PATH}/api"
        kwargs["api_path_strip"] = settings.ROOT_PATH
    return HTMLResponse(prebuilt_html(**kwargs))
