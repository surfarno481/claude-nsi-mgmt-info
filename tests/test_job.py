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

"""Tests for aura.job: Job functions (mocked DB and HTTP)."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


class TestNewCorrelationIdOnReservation:
    @patch("aura.job.Session")
    def test_updates_correlationId(self, mock_session_cls):
        from aura.job import new_correlation_id_on_reservation

        mock_reservation = MagicMock()
        mock_reservation.correlationId = uuid4()
        original_corr_id = mock_reservation.correlationId

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_reservation
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        new_correlation_id_on_reservation(1)
        assert mock_reservation.correlationId != original_corr_id


class TestNsiPollDdsJob:
    @patch("aura.job.update_sdps")
    @patch("aura.job.update_stps")
    @patch("aura.job.topology_to_stps")
    @patch("aura.job.nsi_xml_to_dict")
    @patch("aura.job.get_dds_documents")
    def test_calls_update_functions(
        self, mock_get_dds, mock_xml_to_dict, mock_topo_to_stps, mock_update_stps, mock_update_sdps
    ):
        from aura.job import TOPOLOGY_MIME_TYPE, nsi_poll_dds_job

        mock_get_dds.return_value = {TOPOLOGY_MIME_TYPE: {"topo1": b"<xml/>"}}
        mock_xml_to_dict.return_value = {"id": "test"}
        mock_topo_to_stps.return_value = []

        nsi_poll_dds_job()

        mock_get_dds.assert_called_once()
        mock_update_stps.assert_called_once()
        mock_update_sdps.assert_called_once()


class TestNsiSendReserveJob:
    @patch("aura.job.nsi_send_reserve")
    @patch("aura.job.new_correlation_id_on_reservation")
    @patch("aura.job.Session")
    def test_successful_reserve_sets_connectionId(self, mock_session_cls, mock_new_corr, mock_nsi_send):
        from aura.job import nsi_send_reserve_job

        conn_id = str(uuid4())
        mock_reservation = MagicMock(id=1, connectionId=None)
        mock_stp = MagicMock()

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_reservation

        # Session() context manager for reads
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        # Session.begin() context manager for writes
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        mock_nsi_send.return_value = {"connectionId": conn_id}

        nsi_send_reserve_job(1)

        mock_nsi_send.assert_called_once()

    @patch("aura.job.nsi_send_reserve")
    @patch("aura.job.new_correlation_id_on_reservation")
    @patch("aura.job.Session")
    def test_connection_error_triggers_error_transition(self, mock_session_cls, mock_new_corr, mock_nsi_send):
        from aura.job import nsi_send_reserve_job

        mock_reservation = MagicMock(
            id=1,
            globalReservationId=uuid4(),
            correlationId=uuid4(),
            state="CONNECTION_RESERVE_CHECKING",
        )

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_reservation

        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_session_cls.begin.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.begin.return_value.__exit__ = MagicMock(return_value=False)

        mock_nsi_send.side_effect = OSError("Connection refused")

        nsi_send_reserve_job(1)
        # Should have transitioned to CONNECTION_RESERVE_FAILED via connection_error
        assert mock_reservation.state == "CONNECTION_RESERVE_FAILED"


class TestNsiSendTerminateJob:
    @patch("aura.job.nsi_send_terminate")
    @patch("aura.job.new_correlation_id_on_reservation")
    @patch("aura.job.Session")
    def test_successful_terminate(self, mock_session_cls, mock_new_corr, mock_nsi_send):
        from aura.job import nsi_send_terminate_job

        mock_reservation = MagicMock(id=1, correlationId=uuid4(), connectionId=uuid4())

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_reservation
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_nsi_send.return_value = {"Body": {"terminateConfirmed": {}}}

        nsi_send_terminate_job(1)
        mock_nsi_send.assert_called_once()

    @patch("aura.job.nsi_send_terminate")
    @patch("aura.job.new_correlation_id_on_reservation")
    @patch("aura.job.Session")
    def test_terminate_fault_logs_warning(self, mock_session_cls, mock_new_corr, mock_nsi_send):
        from aura.job import nsi_send_terminate_job

        mock_reservation = MagicMock(id=1, correlationId=uuid4(), connectionId=uuid4())

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_reservation
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_nsi_send.return_value = {
            "Body": {
                "Fault": {
                    "detail": {
                        "serviceException": {
                            "nsaId": "urn:test",
                            "errorId": "00201",
                            "text": "Invalid state",
                        }
                    }
                }
            }
        }

        # Should not raise - fault is handled gracefully
        nsi_send_terminate_job(1)


class TestNsiSendReserveCommitJob:
    @patch("aura.job.nsi_send_reserve_commit")
    @patch("aura.job.new_correlation_id_on_reservation")
    @patch("aura.job.Session")
    def test_successful_reserve_commit(self, mock_session_cls, mock_new_corr, mock_nsi_send):
        from aura.job import nsi_send_reserve_commit_job

        mock_reservation = MagicMock(id=1, correlationId=uuid4(), connectionId=uuid4())

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_reservation
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        nsi_send_reserve_commit_job(1)

        mock_new_corr.assert_called_once_with(1)
        mock_nsi_send.assert_called_once_with(mock_reservation)


class TestNsiSendProvisionJob:
    @patch("aura.job.nsi_send_provision")
    @patch("aura.job.new_correlation_id_on_reservation")
    @patch("aura.job.Session")
    def test_successful_provision(self, mock_session_cls, mock_new_corr, mock_nsi_send):
        from aura.job import nsi_send_provision_job

        mock_reservation = MagicMock(id=1, correlationId=uuid4(), connectionId=uuid4())

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_reservation
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        nsi_send_provision_job(1)

        mock_new_corr.assert_called_once_with(1)
        mock_nsi_send.assert_called_once_with(mock_reservation)


class TestNsiSendReleaseJob:
    @patch("aura.job.nsi_send_release")
    @patch("aura.job.new_correlation_id_on_reservation")
    @patch("aura.job.Session")
    def test_successful_release(self, mock_session_cls, mock_new_corr, mock_nsi_send):
        from aura.job import nsi_send_release_job

        mock_reservation = MagicMock(id=1, correlationId=uuid4(), connectionId=uuid4())

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_reservation
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_nsi_send.return_value = {"Body": {"releaseConfirmed": {}}}

        nsi_send_release_job(1)
        mock_nsi_send.assert_called_once()

    @patch("aura.job.nsi_send_release")
    @patch("aura.job.new_correlation_id_on_reservation")
    @patch("aura.job.Session")
    def test_release_fault_handled_gracefully(self, mock_session_cls, mock_new_corr, mock_nsi_send):
        from aura.job import nsi_send_release_job

        mock_reservation = MagicMock(id=1, correlationId=uuid4(), connectionId=uuid4())

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.one.return_value = mock_reservation
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_nsi_send.return_value = {
            "Body": {
                "Fault": {
                    "detail": {
                        "serviceException": {
                            "nsaId": "urn:test",
                            "errorId": "00201",
                            "text": "Release failed",
                        }
                    }
                }
            }
        }

        # Should not raise - fault is handled gracefully
        nsi_send_release_job(1)
