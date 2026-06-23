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

import asyncio
from datetime import datetime
from typing import AsyncIterable

from fastapi import APIRouter
from fastui import AnyComponent, FastUI
from fastui import components as c
from fastui.events import GoToEvent
from starlette.responses import StreamingResponse

from amiss.db import Session
from amiss.frontend.util import (
    app_page,
    button_row,
    reservation_buttons,
    reservation_header,
    reservation_table,
    reservation_tabs,
)
from amiss.fsm import ConnectionStateMachine
from amiss.model import Log, Reservation

router = APIRouter()


@router.get("", response_model=FastUI, response_model_exclude_none=True)
async def reservations() -> list[AnyComponent]:
    """Redirect to active tab of reservations page."""
    return [c.FireEvent(event=GoToEvent(url="/reservations/active"))]


@router.get("/{id}/", response_model=FastUI, response_model_exclude_none=True)
def reservation_details(id: int) -> list[AnyComponent]:
    """Display reservation details."""
    with Session() as session:
        reservation = session.query(Reservation).filter(Reservation.id == id).one_or_none()  # type: ignore[arg-type]
    if reservation is None:
        return app_page(title=f"No reservation with id {id}.")
    return app_page(
        reservation_buttons(reservation),
        c.Heading(text="Reservation details", level=5),
        c.Details(data=reservation),
        c.Heading(text="SourceStp details", level=5),
        c.Details(data=reservation.sourceStp),
        c.Heading(text="DestStp details", level=5),
        c.Details(data=reservation.destStp),
        title=f"Reservation {reservation.description}",
    )


async def reservation_log_stream(id: int) -> AsyncIterable[str]:
    lines = []
    last_timestamp = datetime.fromtimestamp(0)
    while True:
        await asyncio.sleep(0.5)
        with Session() as session:
            messages = (
                session.query(Log.message, Log.timestamp)  # type: ignore[call-overload]
                .filter(Log.reservation_id == id)
                .filter(Log.timestamp > last_timestamp)
                .all()
            )
        for message, timestamp in messages:
            lines.append(c.Div(components=[c.Text(text=f"{timestamp.isoformat()} - {message}")]))
            last_timestamp = timestamp
        m = FastUI(root=lines)  # type: ignore[arg-type]
        yield f"data: {m.model_dump_json(by_alias=True, exclude_none=True)}\n\n"


@router.get("/{id}/log/sse")
async def reservation_log_sse(id: int) -> StreamingResponse:
    return StreamingResponse(reservation_log_stream(id), media_type="text/event-stream")


@router.get("/{id}/log", response_model=FastUI, response_model_exclude_none=True)
async def reservation_log(id: int) -> list[AnyComponent]:
    """Show streaming log for reservation with given id."""
    with Session() as session:
        reservation = session.query(Reservation).filter(Reservation.id == id).one_or_none()  # type: ignore[arg-type]
    if reservation is None:
        return app_page(title=f"No reservation with id {id}.")
    return app_page(
        button_row(
            [
                c.Button(
                    text="Back",
                    on_click=GoToEvent(url=f"/reservations/{id}/"),
                    class_name="+ ms-2",
                )
            ]
        ),
        reservation_header(reservation),
        c.Div(
            components=[
                c.ServerLoad(
                    path=f"/reservations/{id}/log/sse",
                    sse=True,
                    sse_retry=500,
                ),
            ],
            class_name="my-2 p-2 border rounded",
        ),
        title=f"Streaming logs {reservation.description}",
    )


@router.get("/all", response_model=FastUI, response_model_exclude_none=True)
def reservations_all() -> list[AnyComponent]:
    """Display overview of all reservations."""
    with Session() as session:
        reservations = session.query(Reservation).order_by(Reservation.id).all()
    return app_page(
        *reservation_tabs(),
        reservation_table(reservations),
        title="All reservations",
    )


@router.get("/active", response_model=FastUI, response_model_exclude_none=True)
def reservations_active() -> list[AnyComponent]:
    """Display overview of active reservations."""
    with Session() as session:
        reservations = (
            session.query(Reservation)
            .filter(Reservation.state == ConnectionStateMachine.ConnectionActive.value)
            .order_by(Reservation.id)
            .all()
        )
    return app_page(
        *reservation_tabs(),
        reservation_table(reservations),
        title="Active reservations",
    )


@router.get("/attention", response_model=FastUI, response_model_exclude_none=True)
def reservations_attention() -> list[AnyComponent]:
    """Display overview of reservations that need attention."""
    with Session() as session:
        reservations = (
            session.query(Reservation)
            .filter(
                (Reservation.state != ConnectionStateMachine.ConnectionActive.value)
                & (Reservation.state != ConnectionStateMachine.ConnectionTerminating.value)
                & (Reservation.state != ConnectionStateMachine.ConnectionTerminated.value)
            )
            .order_by(Reservation.id)
            .all()
        )
    return app_page(
        *reservation_tabs(),
        reservation_table(reservations),
        title="Reservations that need attention",
    )
