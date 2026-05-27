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

"""Tests for aura.log: DatabaseLogHandler and UvicornAccessLogFilter."""

from logging import LogRecord
from unittest.mock import MagicMock, patch

import pytest

from aura.log import DatabaseLogHandler, UvicornAccessLogFilter


class TestDatabaseLogHandler:
    @patch("aura.log.Session")
    def test_emit_with_reservationId(self, mock_session_cls):
        handler = DatabaseLogHandler()
        record = LogRecord("test", 20, "test.py", 1, None, (), None)
        record.msg = {"event": "test event", "reservationId": 42}

        mock_session = MagicMock()
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        handler.emit(record)
        mock_session.add.assert_called_once()

    @patch("aura.log.Session")
    def test_emit_without_structlog_dict_skips(self, mock_session_cls):
        handler = DatabaseLogHandler()
        record = LogRecord("test", 20, "test.py", 1, "plain string message", (), None)

        mock_session = MagicMock()
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        handler.emit(record)
        mock_session.add.assert_not_called()

    @patch("aura.log.Session")
    def test_emit_with_no_matching_id_sets_negative(self, mock_session_cls):
        handler = DatabaseLogHandler()
        record = LogRecord("test", 20, "test.py", 1, None, (), None)
        record.msg = {"event": "some event"}

        mock_session = MagicMock()
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        handler.emit(record)
        # reservationId is -1, so add should not be called (reservationId < 0)
        mock_session.add.assert_not_called()

    @patch("aura.log.Session")
    def test_emit_with_connectionId_queries_db(self, mock_session_cls):
        handler = DatabaseLogHandler()
        record = LogRecord("test", 20, "test.py", 1, None, (), None)
        record.msg = {"event": "test", "connectionId": "4f0a4f6b-1187-4670-b451-bb8005105ba5"}

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = 5
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        handler.emit(record)
        mock_session.query.assert_called_once()
        mock_session.add.assert_called_once()

    @patch("aura.log.Session")
    def test_emit_with_globalReservationId_queries_db(self, mock_session_cls):
        handler = DatabaseLogHandler()
        record = LogRecord("test", 20, "test.py", 1, None, (), None)
        record.msg = {"event": "test", "globalReservationId": "4f0a4f6b-1187-4670-b451-bb8005105ba5"}

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = 7
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        handler.emit(record)
        mock_session.query.assert_called_once()
        mock_session.add.assert_called_once()

    @patch("aura.log.Session")
    def test_emit_with_correlationId_queries_db(self, mock_session_cls):
        handler = DatabaseLogHandler()
        record = LogRecord("test", 20, "test.py", 1, None, (), None)
        record.msg = {"event": "test", "correlationId": "4f0a4f6b-1187-4670-b451-bb8005105ba5"}

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = 9
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        handler.emit(record)
        mock_session.query.assert_called_once()
        mock_session.add.assert_called_once()

    @patch("aura.log.Session")
    def test_emit_with_connectionId_none_string_skips_lookup(self, mock_session_cls):
        handler = DatabaseLogHandler()
        record = LogRecord("test", 20, "test.py", 1, None, (), None)
        record.msg = {"event": "test", "connectionId": "None"}

        mock_session = MagicMock()
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        handler.emit(record)
        # connectionId == "None" is explicitly skipped, falls through to reservationId = -1
        mock_session.add.assert_not_called()

    @patch("aura.log.Session")
    def test_emit_with_connectionId_not_found_raises(self, mock_session_cls):
        handler = DatabaseLogHandler()
        record = LogRecord("test", 20, "test.py", 1, None, (), None)
        record.msg = {"event": "test", "connectionId": "4f0a4f6b-1187-4670-b451-bb8005105ba5"}

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.scalar.return_value = None
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        # scalar() returns None when not found; code does `if reservationId >= 0`
        # which raises TypeError comparing None >= 0 (a latent bug)
        with pytest.raises(TypeError, match="not supported between instances of 'NoneType' and 'int'"):
            handler.emit(record)


class TestUvicornAccessLogFilter:
    @pytest.mark.parametrize(
        "args,expected",
        [
            pytest.param(("127.0.0.1", "GET", "/healthcheck"), False, id="healthcheck-filtered"),
            pytest.param(("127.0.0.1", "GET", "/api/reservations"), True, id="other-endpoint-passes"),
            pytest.param(None, True, id="none-args-passes"),
            pytest.param(("127.0.0.1",), True, id="short-args-passes"),
            pytest.param((), True, id="empty-tuple-passes"),
        ],
    )
    def test_filter(self, args, expected):
        filt = UvicornAccessLogFilter()
        record = LogRecord("uvicorn.access", 20, "test.py", 1, "msg", (), None)
        record.args = args
        assert filt.filter(record) is expected
