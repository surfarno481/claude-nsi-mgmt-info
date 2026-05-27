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

"""Tests for aura.fsm: ConnectionStateMachine transitions."""

import pytest
from statemachine.exceptions import TransitionNotAllowed

from aura.fsm import ConnectionStateMachine


VALID_TRANSITIONS = [
    pytest.param("nsi_send_reserve", "CONNECTION_NEW", "CONNECTION_RESERVE_CHECKING", id="new-to-checking"),
    pytest.param(
        "nsi_send_reserve", "CONNECTION_RESERVE_FAILED", "CONNECTION_RESERVE_CHECKING", id="failed-to-checking"
    ),
    pytest.param("nsi_send_reserve", "CONNECTION_TERMINATED", "CONNECTION_RESERVE_CHECKING", id="terminated-to-checking"),
    pytest.param(
        "nsi_receive_reserve_confirmed",
        "CONNECTION_RESERVE_CHECKING",
        "RESERVE_HELD",
        id="checking-to-held",
    ),
    pytest.param(
        "nsi_receive_reserve_failed",
        "CONNECTION_RESERVE_CHECKING",
        "CONNECTION_RESERVE_FAILED",
        id="checking-to-failed",
    ),
    pytest.param(
        "connection_error", "CONNECTION_RESERVE_CHECKING", "CONNECTION_RESERVE_FAILED", id="checking-error-to-failed"
    ),
    pytest.param(
        "nsi_receive_reserve_timeout", "RESERVE_HELD", "CONNECTION_RESERVE_TIMEOUT", id="held-to-timeout"
    ),
    pytest.param(
        "nsi_send_reserve_commit", "RESERVE_HELD", "CONNECTION_RESERVE_COMMITTING", id="held-to-committing"
    ),
    pytest.param(
        "nsi_receive_reserve_commit_confirmed",
        "CONNECTION_RESERVE_COMMITTING",
        "CONNECTION_RESERVE_COMMITTED",
        id="committing-to-committed",
    ),
    pytest.param(
        "nsi_send_provision", "CONNECTION_RESERVE_COMMITTED", "CONNECTION_PROVISIONING", id="committed-to-provisioning"
    ),
    pytest.param(
        "nsi_receive_provision_confirmed",
        "CONNECTION_PROVISIONING",
        "CONNECTION_PROVISIONED",
        id="provisioning-to-provisioned",
    ),
    pytest.param("nsi_send_release", "CONNECTION_ACTIVE", "CONNECTION_RELEASING", id="active-to-releasing"),
    pytest.param(
        "nsi_receive_release_confirmed", "CONNECTION_RELEASING", "CONNECTION_RELEASED", id="releasing-to-released"
    ),
    pytest.param(
        "nsi_receive_data_plane_up", "CONNECTION_PROVISIONED", "CONNECTION_ACTIVE", id="provisioned-to-active"
    ),
    pytest.param(
        "nsi_receive_data_plane_down",
        "CONNECTION_RELEASED",
        "CONNECTION_RESERVE_COMMITTED",
        id="released-to-committed",
    ),
    pytest.param(
        "nsi_receive_error_event", "CONNECTION_ACTIVE", "CONNECTION_FAILED", id="active-error-to-failed"
    ),
    pytest.param(
        "nsi_receive_error_event", "CONNECTION_PROVISIONING", "CONNECTION_FAILED", id="provisioning-error-to-failed"
    ),
    pytest.param(
        "nsi_receive_error_event", "CONNECTION_PROVISIONED", "CONNECTION_FAILED", id="provisioned-error-to-failed"
    ),
    pytest.param(
        "nsi_send_terminate",
        "CONNECTION_RESERVE_TIMEOUT",
        "CONNECTION_TERMINATING",
        id="timeout-to-terminating",
    ),
    pytest.param(
        "nsi_send_terminate",
        "CONNECTION_RESERVE_COMMITTED",
        "CONNECTION_TERMINATING",
        id="committed-to-terminating",
    ),
    pytest.param(
        "nsi_send_terminate", "CONNECTION_PROVISIONED", "CONNECTION_TERMINATING", id="provisioned-to-terminating"
    ),
    pytest.param(
        "nsi_send_terminate", "CONNECTION_FAILED", "CONNECTION_TERMINATING", id="failed-to-terminating"
    ),
    pytest.param(
        "nsi_send_terminate",
        "CONNECTION_RESERVE_FAILED",
        "CONNECTION_TERMINATING",
        id="reserve-failed-to-terminating",
    ),
    pytest.param(
        "nsi_receive_terminate_confirmed",
        "CONNECTION_TERMINATING",
        "CONNECTION_TERMINATED",
        id="terminating-to-terminated",
    ),
    pytest.param(
        "gui_delete_connection", "CONNECTION_TERMINATED", "CONNECTION_DELETED", id="terminated-to-deleted"
    ),
]


class TestConnectionStateMachineTransitions:
    @pytest.mark.parametrize("event,source_state,target_state", VALID_TRANSITIONS)
    def test_valid_transition(self, event, source_state, target_state, reservation_factory):
        reservation = reservation_factory(state=source_state)
        csm = ConnectionStateMachine(reservation)
        getattr(csm, event)()
        assert reservation.state == target_state

    @pytest.mark.parametrize(
        "event,invalid_source_state",
        [
            pytest.param("nsi_send_provision", "CONNECTION_NEW", id="provision-from-new"),
            pytest.param("nsi_send_release", "CONNECTION_NEW", id="release-from-new"),
            pytest.param("nsi_receive_data_plane_up", "CONNECTION_NEW", id="dataplane-up-from-new"),
            pytest.param("gui_delete_connection", "CONNECTION_NEW", id="delete-from-new"),
            pytest.param("nsi_send_reserve_commit", "CONNECTION_NEW", id="commit-from-new"),
            pytest.param("nsi_send_release", "CONNECTION_PROVISIONING", id="release-from-provisioning"),
            pytest.param("nsi_receive_data_plane_up", "CONNECTION_PROVISIONING", id="dataplane-up-from-provisioning"),
            pytest.param("nsi_send_reserve", "CONNECTION_PROVISIONED", id="reserve-from-provisioned"),
            pytest.param("nsi_receive_data_plane_down", "CONNECTION_PROVISIONED", id="dataplane-down-from-provisioned"),
            pytest.param("nsi_send_reserve", "CONNECTION_ACTIVE", id="reserve-from-active"),
            pytest.param("nsi_receive_data_plane_up", "CONNECTION_ACTIVE", id="dataplane-up-from-active"),
            pytest.param("nsi_send_reserve", "CONNECTION_RELEASED", id="reserve-from-released"),
            pytest.param("nsi_send_terminate", "CONNECTION_RELEASING", id="terminate-from-releasing"),
            pytest.param("gui_delete_connection", "CONNECTION_DELETED", id="delete-from-deleted"),
        ],
    )
    def test_invalid_transition_raises(self, event, invalid_source_state, reservation_factory):
        reservation = reservation_factory(state=invalid_source_state)
        csm = ConnectionStateMachine(reservation)
        with pytest.raises(TransitionNotAllowed):
            getattr(csm, event)()


class TestConnectionStateMachineProperties:
    def test_initial_state(self, reservation_factory):
        reservation = reservation_factory(state="CONNECTION_NEW")
        csm = ConnectionStateMachine(reservation)
        assert csm.ConnectionNew.is_active

    def test_final_state_is_deleted(self):
        assert ConnectionStateMachine.ConnectionDeleted.final

    def test_active_state_values_complete(self):
        active = set(ConnectionStateMachine.active_state_values)
        expected = {
            "CONNECTION_PROVISIONED",
            "CONNECTION_RELEASED",
            "CONNECTION_ACTIVE",
            "CONNECTION_FAILED",
            "CONNECTION_RESERVE_CHECKING",
            "RESERVE_HELD",
            "CONNECTION_RESERVE_COMMITTING",
            "CONNECTION_RESERVE_COMMITTED",
            "CONNECTION_PROVISIONING",
            "CONNECTION_RELEASING",
            "CONNECTION_TERMINATING",
        }
        assert active == expected

    def test_active_state_values_excludes_terminal(self):
        active = ConnectionStateMachine.active_state_values
        assert "CONNECTION_NEW" not in active
        assert "CONNECTION_TERMINATED" not in active
        assert "CONNECTION_DELETED" not in active
        assert "CONNECTION_RESERVE_FAILED" not in active
        assert "CONNECTION_RESERVE_TIMEOUT" not in active


class TestConnectionStateMachineFullPath:
    def test_happy_path_reserve_to_terminate(self, reservation_factory):
        reservation = reservation_factory(state="CONNECTION_NEW")
        csm = ConnectionStateMachine(reservation)
        csm.nsi_send_reserve()
        assert reservation.state == "CONNECTION_RESERVE_CHECKING"
        csm.nsi_receive_reserve_confirmed()
        assert reservation.state == "RESERVE_HELD"
        csm.nsi_send_reserve_commit()
        assert reservation.state == "CONNECTION_RESERVE_COMMITTING"
        csm.nsi_receive_reserve_commit_confirmed()
        assert reservation.state == "CONNECTION_RESERVE_COMMITTED"
        csm.nsi_send_provision()
        assert reservation.state == "CONNECTION_PROVISIONING"
        csm.nsi_receive_provision_confirmed()
        assert reservation.state == "CONNECTION_PROVISIONED"
        csm.nsi_receive_data_plane_up()
        assert reservation.state == "CONNECTION_ACTIVE"
        csm.nsi_send_release()
        assert reservation.state == "CONNECTION_RELEASING"
        csm.nsi_receive_release_confirmed()
        assert reservation.state == "CONNECTION_RELEASED"
        csm.nsi_receive_data_plane_down()
        assert reservation.state == "CONNECTION_RESERVE_COMMITTED"
        csm.nsi_send_terminate()
        assert reservation.state == "CONNECTION_TERMINATING"
        csm.nsi_receive_terminate_confirmed()
        assert reservation.state == "CONNECTION_TERMINATED"
        csm.gui_delete_connection()
        assert reservation.state == "CONNECTION_DELETED"
