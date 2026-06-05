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

from amiss.frontend.util import app_page
from amiss.settings import settings

router = APIRouter()

introduction = """
[AMISS](https://github.com/workfloworchestrator/nsi-mgmt-info/),
the Network Service Interface (NSI) Management Information System (MIS)
for the [Advanced North Atlantic (ANA) consortium](https://www.anaeng.global/).
This is part of a project called ANA-GRAM, the ANA Global Resource Aggregation Method,
to federate and manage the ANA trans-Atlantic links via network automation.
"""

how_to = """
* [Active Reservations](/reservations/active).
* [Active Termination Points ](/stp/active).
* [Active Demarcation Points ](/sdp/active).
* [Active Reservations per link](/spectrum/active).
"""

@router.get("/", response_model=FastUI, response_model_exclude_none=True)
def home() -> list[AnyComponent]:
    # Arno: Topologies are now pulled via __init__.py on a 1 minute interval.
    return app_page(
        c.Heading(text="Introduction", level=3),
        c.Markdown(text=introduction),
        c.Heading(text="System Resources", level=3),
        c.Markdown(text=how_to),
    )
