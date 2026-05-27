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
from typing import Annotated

from fastapi import APIRouter
from fastui import AnyComponent, FastUI
from fastui import components as c
from fastui.components import FireEvent
from fastui.events import GoToEvent
from fastui.forms import fastui_form
from pydantic import BaseModel, Field

from aura.db import Session
from aura.frontend.util import app_page, button_row, sdp_table
from aura.model import SDP

router = APIRouter()


@router.get("", response_model=FastUI, response_model_exclude_none=True)
async def sdp() -> list[AnyComponent]:
    """Redirect to active tab of sdp page."""
    return [c.FireEvent(event=GoToEvent(url="/sdp/active"))]


@router.get("/active", response_model=FastUI, response_model_exclude_none=True)
def sdp_active() -> list[AnyComponent]:
    """Display all active SDP in a table."""
    with Session() as session:
        sdps = session.query(SDP).filter(SDP.active).order_by(SDP.id).all()
    return app_page(
        *tabs(),
        sdp_table(sdps),
        title="Active Service Demarcation Points",
    )


@router.get("/inactive", response_model=FastUI, response_model_exclude_none=True)
def sdp_inactive() -> list[AnyComponent]:
    """Display all inactive SDP in a table."""
    with Session() as session:
        sdps = session.query(SDP).filter(not SDP.active).order_by(SDP.id).all()
    return app_page(
        *tabs(),
        sdp_table(sdps),
        title="Inctive Service Demarcation Points",
    )


@router.get("/all", response_model=FastUI, response_model_exclude_none=True)
def sdp_all() -> list[AnyComponent]:
    """Display all SDP in a table."""
    with Session() as session:
        sdps = session.query(SDP).order_by(SDP.id).all()
    return app_page(
        *tabs(),
        sdp_table(sdps),
        title="All Service Demarcation Points",
    )


@router.get("/{id}/", response_model=FastUI, response_model_exclude_none=True)
def sdp_detail(id: int) -> list[AnyComponent]:
    """Display sdp details and action buttons."""
    with Session() as session:
        sdp = session.query(SDP).filter(SDP.id == id).one_or_none()  # type: ignore[arg-type]
    if sdp is None:
        return app_page(title=f"No SDP with id {id}.")
    return app_page(
        button_row(
            [
                c.Button(
                    text="Back",
                    on_click=GoToEvent(url="/sdp"),
                    class_name="+ ms-2",
                ),
                # c.Button(
                #     text="Modify",
                #     on_click=GoToEvent(url=f"/sdp/{id}/modify"),
                #     class_name="+ ms-2",
                # ),
            ]
        ),
        c.Heading(text="SDP details", level=4),
        c.Details(data=sdp),
        c.Heading(text="StpA details", level=4),
        c.Details(data=sdp.stpA),
        c.Heading(text="StpZ details", level=4),
        c.Details(data=sdp.stpZ),
        title=f"SDP {sdp.description}",
    )


# @router.get("/{id}/modify", response_model=FastUI, response_model_exclude_none=True)
# def sdp_modify_form(id: int) -> list[AnyComponent]:
#     with Session() as session:
#         sdp = session.query(SDP).filter(SDP.id == id).one_or_none()  # type: ignore[arg-type]
#     if sdp is None:
#         return app_page(title=f"No SDP with id {id}.")
#
#     class SdpModifyForm(BaseModel):
#         description: str = Field(default=sdp.description, title="Description")
#
#     """Render modify input form."""
#     submit_url = f"/api/sdp/{sdp.id}/update"
#     return app_page(
#         c.Heading(text=f"{sdp.stpAId} <-> {sdp.stpZId}", level=4),
#         c.ModelForm(model=SdpModifyForm, submit_url=submit_url, display_mode="default"),
#         title="Modify SDP",
#     )


class SdpUpdateForm(BaseModel):
    description: str = Field()


@router.post("/{id}/update", response_model=FastUI, response_model_exclude_none=True)
def sdp_update(id: int, form: Annotated[SdpUpdateForm, fastui_form(SdpUpdateForm)]) -> list[FireEvent]:
    with Session.begin() as session:
        sdp = session.query(SDP).filter(SDP.id == id).one_or_none()
        if sdp is not None:
            sdp.description = form.description
    return [c.FireEvent(event=GoToEvent(url=f"/sdp/{id}/"))]


def tabs() -> list[AnyComponent]:
    return [
        c.LinkList(
            links=[
                c.Link(
                    components=[c.Text(text="Active")],
                    on_click=GoToEvent(url="/sdp/active"),
                    active="startswith:/sdp/active",
                ),
                c.Link(
                    components=[c.Text(text="Inactive")],
                    on_click=GoToEvent(url="/sdp/inactive"),
                    active="startswith:/sdp/inactive",
                ),
                c.Link(
                    components=[c.Text(text="All")],
                    on_click=GoToEvent(url="/sdp/all"),
                    active="startswith:/sdp/all",
                ),
            ],
            mode="tabs",
            class_name="+ mb-4",
        ),
    ]
