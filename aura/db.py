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
from sqlmodel import create_engine

from aura.model import SQLModel
from aura.settings import settings

logger = structlog.get_logger(__name__)

log = logger.bind(database_uri=settings.DATABASE_URI)
if (parse_result := urlparse(settings.DATABASE_URI)).scheme not in ("sqlite", "postgresql"):
    log.error("Database engine not supported.", engine=parse_result.scheme)
    exit(1)
log.info("Create database connection.")
try:
    engine = create_engine(settings.DATABASE_URI, echo=settings.SQL_LOGGING)
    SQLModel.metadata.create_all(engine)
except OperationalError as e:
    log.error("Failed to create database connection.", reason=e)
    exit(1)
Session = sessionmaker(engine)
