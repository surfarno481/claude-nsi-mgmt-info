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
from urllib.parse import urlparse

import structlog
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from amiss.model import SQLModel
from amiss.settings import settings

logger = structlog.get_logger(__name__)

log = logger.bind(database_uri=settings.DATABASE_URI)
if (parse_result := urlparse(settings.DATABASE_URI)).scheme not in ("sqlite", "postgresql"):
    log.error("Database engine not supported.", engine=parse_result.scheme)
    exit(1)
log.info("Create database connection.")
# A shared in-memory SQLite database only lives while a connection is held open, and this app is
# multi-threaded (APScheduler workers + FastAPI). Use a StaticPool (a single, long-lived connection
# shared across threads) for in-memory SQLite so tables created by create_all() do not vanish when
# pooled connections recycle and worker threads do not raise check_same_thread errors. File-based
# SQLite and PostgreSQL keep the default pool.
engine_kwargs: dict = {"echo": settings.SQL_LOGGING}
is_memory = parse_result.scheme == "sqlite" and (
    "memory" in settings.DATABASE_URI or settings.DATABASE_URI in ("sqlite://", "sqlite:///:memory:")
)
if is_memory:
    engine_kwargs["poolclass"] = StaticPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}
try:
    engine = create_engine(settings.DATABASE_URI, **engine_kwargs)
    SQLModel.metadata.create_all(engine)
except OperationalError as e:
    log.error("Failed to create database connection.", reason=e)
    exit(1)
Session = sessionmaker(engine)
