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

from fastapi import APIRouter
from fastui import AnyComponent, FastUI
from fastui import components as c
from fastui.events import GoToEvent

from aura.frontend.util import app_page
from aura.settings import settings

router = APIRouter()

introduction = """
[NSI-AuRA](https://github.com/workfloworchestrator/nsi-aura/),
the Network Service Interface (NSI) ultimate Requester Agent (uRA)
for the [Advanced North Atlantic (ANA) consortium](https://www.anaeng.global/).
This is part of a project called ANA-GRAM, the ANA Global Resource Aggregation Method,
to federate the ANA trans-Atlantic links via network automation.
"""

how_to = """
1. Mail NOC of domain A and Z to determine Customer VLAN IDs and add matching endpoints to their NSI domain topologies.
2. Allow the topology change(s) to propagate.
3. [Select endpoints and transatlantic link](/reservations/new).
"""

@router.get("/", response_model=FastUI, response_model_exclude_none=True)
def home() -> list[AnyComponent]:
    # Arno: Topologies are now pulled via __init__.py on a 1 minute interval.
    return app_page(
        c.Heading(text="Introduction", level=3),
        c.Markdown(text=introduction),
        c.Heading(text="Connection states and operations", level=3),
        c.Div(
            components=[
                c.Image(
                    src=f"{settings.ROOT_PATH}/static/AuRA Reservation States.svg",
                    alt="AURA Connection State and Actions diagram",
                    loading="lazy",
                    referrer_policy="no-referrer",
                )
            ],
            class_name="+ d-flex justify-content-center",
        ),
        c.Heading(text="How to Create a New Connection", level=3),
        c.Markdown(text=how_to),
        c.Heading(text="Other Operations?", level=3),
        c.Paragraph(text="See buttons at top of page."),
    )
