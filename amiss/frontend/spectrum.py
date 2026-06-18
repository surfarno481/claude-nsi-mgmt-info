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

# Arno TODO:
# * Retrieve Spans for all or a given Reservation from Aggregator Proxy, and store in DB
# * Or: Live Retrieve Spans for all reservations, figure out which reservations use the same spectrum, show in spectrum detail view.
#
# Use https://github.com/workfloworchestrator/nsi-aggregator-proxy#get-reservationsconnectionid
# with the "detail" parameter set to "full".
#
# Refactor:
# * Talk to DDS-Proxy instead of DDS directly to get STP and SDP.
# *

from typing import Annotated

from fastapi import APIRouter
from fastui import AnyComponent, FastUI
from fastui import components as c
from fastui.components import FireEvent
from fastui.events import GoToEvent
from fastui.forms import fastui_form
from pydantic import BaseModel, Field

from amiss.db import Session
from amiss.frontend.util import app_page, button_row, spectrum_table, segment_table
from amiss.model import SDP, Segment

router = APIRouter()


@router.get("", response_model=FastUI, response_model_exclude_none=True)
async def spectrum() -> list[AnyComponent]:
    """Redirect to active tab of spectrum page."""
    return [c.FireEvent(event=GoToEvent(url="/spectrum/active"))]


@router.get("/active", response_model=FastUI, response_model_exclude_none=True)
def spectrum_active() -> list[AnyComponent]:
    """Display all active SDP in a table."""
    with Session() as session:
        sdps = session.query(SDP).filter(SDP.active).order_by(SDP.id).all()
    return app_page(
        *tabs(),
        spectrum_table(sdps),
        title="Active Spectra",
    )


@router.get("/inactive", response_model=FastUI, response_model_exclude_none=True)
def spectrum_inactive() -> list[AnyComponent]:
    """Display all inactive SDP in a table."""
    with Session() as session:
        sdps = session.query(SDP).filter(not SDP.active).order_by(SDP.id).all()
    return app_page(
        *tabs(),
        spectrum_table(sdps),
        title="Inactive Spectra",
    )


@router.get("/all", response_model=FastUI, response_model_exclude_none=True)
def spectrum_all() -> list[AnyComponent]:
    """Display all SDP in a table."""
    with Session() as session:
        sdps = session.query(SDP).order_by(SDP.id).all()
    return app_page(
        *tabs(),
        spectrum_table(sdps),
        title="All Spectra",
    )


@router.get("/{id}/", response_model=FastUI, response_model_exclude_none=True)
def spectrum_detail(id: int) -> list[AnyComponent]:
    """Display spectrum details and action buttons."""
    with Session() as session:
        sdp = session.query(SDP).filter(SDP.id == id).one_or_none()  # type: ignore[arg-type]
        if sdp is None:
            return app_page(title=f"No SDP with id {id}.")
        want_sdp_ids = [sdp.stpA.stpId, sdp.stpZ.stpId]
        segments = session.query(Segment).all()

    # Keep the segments whose source STP (minus any ?vlan=... suffix) is one of this SDP's STPs.
    spectrum_segments = [
        segment
        for segment in segments
        if (segment.sourceStp.split("?")[0] if "?" in segment.sourceStp else segment.sourceStp) in want_sdp_ids
    ]

    segtable = segment_table(spectrum_segments)

    return app_page(
        button_row(
            [
                c.Button(
                    text="Back",
                    on_click=GoToEvent(url="/spectrum"),
                    class_name="+ ms-2",
                ),
            ]
        ),
        c.Heading(text="SDP details", level=4),
        c.Details(data=sdp),
        c.Heading(text="Reservations on this link", level=4),
        segtable,
        title=f"SDP {sdp.description}",
    )


class SpectrumUpdateForm(BaseModel):
    description: str = Field()


@router.post("/{id}/update", response_model=FastUI, response_model_exclude_none=True)
def spectrum_update(id: int, form: Annotated[SpectrumUpdateForm, fastui_form(SpectrumUpdateForm)]) -> list[FireEvent]:
    with Session.begin() as session:
        sdp = session.query(SDP).filter(SDP.id == id).one_or_none()
        if sdp is not None:
            sdp.description = form.description
    return [c.FireEvent(event=GoToEvent(url=f"/spectrum/{id}/"))]


def tabs() -> list[AnyComponent]:
    return [
        c.LinkList(
            links=[
                c.Link(
                    components=[c.Text(text="Active")],
                    on_click=GoToEvent(url="/spectrum/active"),
                    active="startswith:/spectrum/active",
                ),
                c.Link(
                    components=[c.Text(text="Inactive")],
                    on_click=GoToEvent(url="/spectrum/inactive"),
                    active="startswith:/spectrum/inactive",
                ),
                c.Link(
                    components=[c.Text(text="All")],
                    on_click=GoToEvent(url="/spectrum/all"),
                    active="startswith:/spectrum/all",
                ),
            ],
            mode="tabs",
            class_name="+ mb-4",
        ),
    ]
