# Copyright 2024-2026 SURF.
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

"""Root test configuration and shared fixtures."""

import logging
import os
from pathlib import Path

# Must set DATABASE_URI and create dummy PEM files before any amiss module imports
# trigger settings/db initialization (Settings validates FilePath at import time)
os.environ["DATABASE_URI"] = "sqlite://"
for _pem in ("amiss-certificate.pem", "amiss-private-key.pem"):
    Path(_pem).touch(exist_ok=True)

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session as SQLModelSession, SQLModel, create_engine

from amiss.log import DatabaseLogHandler
from amiss.model import SDP, STP, Reservation, Segment


def _disable_database_log_handler():
    """Remove DatabaseLogHandler from all loggers to prevent DB calls during tests."""
    root_logger = logging.getLogger()
    root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, DatabaseLogHandler)]
    for logger_name in list(logging.Logger.manager.loggerDict):
        logger = logging.getLogger(logger_name)
        logger.handlers = [h for h in logger.handlers if not isinstance(h, DatabaseLogHandler)]


_disable_database_log_handler()


@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite engine for the entire test session."""
    eng = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db_session(engine):
    """Per-test database session with automatic rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SQLModelSession(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def stp_factory():
    """Factory for creating STP instances."""

    def _make_stp(**kwargs):
        defaults = {
            "stpId": "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
            "inboundPort": None,
            "outboundPort": None,
            "inboundAlias": None,
            "outboundAlias": None,
            "vlanRange": "100-200",
            "description": "Test STP",
            "active": True,
        }
        defaults.update(kwargs)
        return STP(**defaults)

    return _make_stp


@pytest.fixture()
def sdp_factory():
    """Factory for creating SDP instances."""

    def _make_sdp(**kwargs):
        defaults = {
            "stpAId": 1,
            "stpZId": 2,
            "vlanRange": "100-200",
            "description": "Test SDP",
            "active": True,
        }
        defaults.update(kwargs)
        return SDP(**defaults)

    return _make_sdp


@pytest.fixture()
def segment_factory():
    """Factory for creating Segment instances."""

    def _make_segment(**kwargs):
        defaults = {
            "connectionId": "child-seg-0",
            "reservation_id": 1,
            "order": 0,
            "providerNSA": "SupaDuppa",
            "serviceType": "EVTS.A-GOLE",
            "capacity": 32768,
            "sourceStp": "internet2.edu:2025:ana:manlan.ps1",
            "destStp": "surf.nl:2020:ana:netherlight.ps1",
            "status": "ACTIVE",
        }
        defaults.update(kwargs)
        return Segment(**defaults)

    return _make_segment


@pytest.fixture()
def reservation_factory():
    """Factory for creating Reservation instances."""

    def _make_reservation(**kwargs):
        defaults = {
            "connectionId": uuid4(),
            "globalReservationId": uuid4(),
            "correlationId": uuid4(),
            "description": "Test reservation",
            "startTime": datetime.now(timezone.utc),
            "endTime": datetime.now(timezone.utc),
            "sourceStpId": 1,
            "destStpId": 2,
            "sourceVlan": 100,
            "destVlan": 200,
            "bandwidth": 1000,
            "state": "CONNECTION_NEW",
        }
        defaults.update(kwargs)
        return Reservation(**defaults)

    return _make_reservation
