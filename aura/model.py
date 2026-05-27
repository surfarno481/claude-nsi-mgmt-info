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

from datetime import datetime
from typing import Annotated
from uuid import UUID

from annotated_types import Ge, Gt, Le, doc
from sqlmodel import Field, Relationship, SQLModel

#
# Types
#
Vlan = Annotated[int, Ge(2), Le(4094), doc("VLAN ID.")]
Bandwidth = Annotated[int, Gt(0)]


#
# Models
#
class STP(SQLModel, table=True):
    """NSI Service Termination Point."""

    id: int | None = Field(default=None, primary_key=True)
    stpId: str
    inboundPort: str | None
    outboundPort: str | None
    inboundAlias: str | None
    outboundAlias: str | None
    vlanRange: str  # our labels are VLAN's
    description: str | None
    active: bool = Field(default=True)

    @property
    def organisationId(self) -> str:
        _, _, _, fqdn, date, *opaque_part = self.stpId.split(":")
        return fqdn + ":" + date

    @property
    def networkId(self) -> str:
        _, _, _, fqdn, date, *opaque_part = self.stpId.split(":")
        return opaque_part[0]

    @property
    def localId(self) -> str:
        _, _, _, fqdn, date, *opaque_part = self.stpId.split(":")
        return ":".join(opaque_part[1:])

    @property
    def urn_base(self) -> str:
        return f"urn:ogf:network:{self.stpId}"

    @property
    def urn(self) -> str:
        return f"{self.urn_base}?vlan={self.vlanRange}"


class ReservationSDPLink(SQLModel, table=True):
    reservation_id: int | None = Field(default=None, foreign_key="reservation.id", primary_key=True)
    sdp_id: int | None = Field(default=None, foreign_key="sdp.id", primary_key=True)


class SDP(SQLModel, table=True):
    """NSI Service Demarcation Point."""

    id: int | None = Field(default=None, primary_key=True)
    stpAId: int = Field(foreign_key="stp.id")
    stpZId: int = Field(foreign_key="stp.id")
    vlanRange: str  # our labels are VLAN's
    description: str | None
    active: bool = Field(default=True)

    stpA: STP = Relationship(sa_relationship_kwargs={"primaryjoin": "SDP.stpAId == STP.id", "lazy": "joined"})
    stpZ: STP = Relationship(sa_relationship_kwargs={"primaryjoin": "SDP.stpZId == STP.id", "lazy": "joined"})

    reservations: list["Reservation"] = Relationship(back_populates="sdps", link_model=ReservationSDPLink)


class Reservation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    connectionId: UUID | None
    globalReservationId: UUID
    correlationId: UUID
    description: str
    startTime: datetime | None = None
    endTime: datetime | None = None
    sourceStpId: int = Field(foreign_key="stp.id")
    destStpId: int = Field(foreign_key="stp.id")
    sourceVlan: Vlan
    destVlan: Vlan
    bandwidth: Bandwidth
    state: str  # Statemachine default state field name
    # state: str = Field(default=ConnectionStateMachine.ConnectionNew.value) # need to fix circular imports to use this

    sdps: list[SDP] = Relationship(back_populates="reservations", link_model=ReservationSDPLink)
    sourceStp: STP = Relationship(
        sa_relationship_kwargs={"primaryjoin": "Reservation.sourceStpId == STP.id", "lazy": "joined"}
    )
    destStp: STP = Relationship(
        sa_relationship_kwargs={"primaryjoin": "Reservation.destStpId == STP.id", "lazy": "joined"}
    )


class Log(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    reservation_id: int = Field(foreign_key="reservation.id")
    name: str
    module: str
    line: int
    function: str
    filename: str
    timestamp: datetime
    message: str
