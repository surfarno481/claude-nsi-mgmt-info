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
from aura.frontend.util import app_page, button_row, stp_table
from aura.model import STP

router = APIRouter()


@router.get("", response_model=FastUI, response_model_exclude_none=True)
async def stp() -> list[AnyComponent]:
    """Redirect to active tab of stp page."""
    return [c.FireEvent(event=GoToEvent(url="/stp/active"))]


@router.get("/active", response_model=FastUI, response_model_exclude_none=True)
def stp_active() -> list[AnyComponent]:
    """Display all active STP in a table."""
    with Session() as session:
        stps = session.query(STP).filter(STP.active).order_by(STP.id).all()
    return app_page(
        *tabs(),
        stp_table(stps),
        title="Active Service Termination Points",
    )


@router.get("/inactive", response_model=FastUI, response_model_exclude_none=True)
def stp_inactive() -> list[AnyComponent]:
    """Display all inactive STP in a table."""
    with Session() as session:
        stps = session.query(STP).filter(not STP.active).order_by(STP.id).all()
    return app_page(
        *tabs(),
        stp_table(stps),
        title="Inctive Service Termination Points",
    )


@router.get("/all", response_model=FastUI, response_model_exclude_none=True)
def stp_all() -> list[AnyComponent]:
    """Display all STP in a table."""
    with Session() as session:
        stps = session.query(STP).order_by(STP.id).all()
    return app_page(
        *tabs(),
        stp_table(stps),
        title="All Service Termination Points",
    )


@router.get("/{id}/", response_model=FastUI, response_model_exclude_none=True)
def stp_detail(id: int) -> list[AnyComponent]:
    """Display stp details and action buttons."""
    with Session() as session:
        stp = session.query(STP).filter(STP.id == id).one_or_none()  # type: ignore[arg-type]
    if stp is None:
        return app_page(title=f"No STP with id {id}.")
    return app_page(
        button_row(
            [
                c.Button(
                    text="Back",
                    on_click=GoToEvent(url="/stp"),
                    class_name="+ ms-2",
                ),
                # c.Button(
                #     text="Modify",
                #     on_click=GoToEvent(url=f"/stp/{id}/modify"),
                #     class_name="+ ms-2",
                # ),
            ]
        ),
        c.Details(data=stp),
        title=f"STP {stp.description}",
    )


# @router.get("/{id}/modify", response_model=FastUI, response_model_exclude_none=True)
# def stp_modify_form(id: int) -> list[AnyComponent]:
#     with Session() as session:
#         stp = session.query(STP).filter(STP.id == id).one_or_none()  # type: ignore[arg-type]
#     if stp is None:
#         return app_page(title=f"No STP with id {id}.")
#
#     class StpModifyForm(BaseModel):
#         description: str = Field(default=stp.description, title="Description")
#
#     """Render modify input form."""
#     submit_url = f"/api/stp/{stp.id}/update"
#     return app_page(
#         c.Heading(text=stp.stpId, level=4),
#         c.ModelForm(model=StpModifyForm, submit_url=submit_url, display_mode="default"),
#         title="Modify STP",
#     )


class StpUpdateForm(BaseModel):
    description: str = Field()


@router.post("/{id}/update", response_model=FastUI, response_model_exclude_none=True)
def stp_update(id: int, form: Annotated[StpUpdateForm, fastui_form(StpUpdateForm)]) -> list[FireEvent]:
    with Session.begin() as session:
        stp = session.query(STP).filter(STP.id == id).one_or_none()
        if stp is not None:
            stp.description = form.description
    return [c.FireEvent(event=GoToEvent(url=f"/stp/{id}/"))]


def tabs() -> list[AnyComponent]:
    return [
        c.LinkList(
            links=[
                c.Link(
                    components=[c.Text(text="Active")],
                    on_click=GoToEvent(url="/stp/active"),
                    active="startswith:/stp/active",
                ),
                c.Link(
                    components=[c.Text(text="Inactive")],
                    on_click=GoToEvent(url="/stp/inactive"),
                    active="startswith:/stp/inactive",
                ),
                c.Link(
                    components=[c.Text(text="All")],
                    on_click=GoToEvent(url="/stp/all"),
                    active="startswith:/stp/all",
                ),
            ],
            mode="tabs",
            class_name="+ mb-4",
        ),
    ]
