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

"""Tests for aura.frontend.util: to_aura_connection_state and reservation_buttons."""

import pytest

from aura.frontend.util import to_aura_connection_state


class TestToAuraConnectionState:
    """Test all branches of to_aura_connection_state mapping."""

    @pytest.mark.parametrize(
        "nsi_states,expected",
        [
            # Lifecycle-driven states
            pytest.param(
                {
                    "lifecycleState": "Terminated",
                    "reservationState": "X",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_TERMINATED",
                id="lifecycle-terminated",
            ),
            pytest.param(
                {
                    "lifecycleState": "Terminating",
                    "reservationState": "X",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_TERMINATING",
                id="lifecycle-terminating",
            ),
            pytest.param(
                {
                    "lifecycleState": "Failed",
                    "reservationState": "X",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_FAILED",
                id="lifecycle-failed",
            ),
            pytest.param(
                {
                    "lifecycleState": "PassedEndTime",
                    "reservationState": "X",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "UNKNOWN",
                id="lifecycle-passed-end-time-unimplemented",
            ),
            # Reservation-driven states (lifecycleState == "Created")
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveChecking",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_RESERVE_CHECKING",
                id="reserve-checking",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveHeld",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "RESERVE_HELD",
                id="reserve-held",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveCommitting",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_RESERVE_COMMITTING",
                id="reserve-committing",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveFailed",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_RESERVE_FAILED",
                id="reserve-failed",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveTimeout",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_RESERVE_TIMEOUT",
                id="reserve-timeout",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveAborting",
                    "provisionState": "X",
                    "dataPlaneStatus": {"active": "false"},
                },
                "UNKNOWN",
                id="reserve-aborting-unimplemented",
            ),
            # Provision-driven states (reservationState == "ReserveStart")
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveStart",
                    "provisionState": "Provisioning",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_PROVISIONING",
                id="provisioning",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveStart",
                    "provisionState": "Releasing",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_RELEASING",
                id="releasing",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveStart",
                    "provisionState": "Provisioned",
                    "dataPlaneStatus": {"active": "true"},
                },
                "CONNECTION_ACTIVE",
                id="provisioned-active-dataplane",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveStart",
                    "provisionState": "Provisioned",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_PROVISIONED",
                id="provisioned-inactive-dataplane",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveStart",
                    "provisionState": "Released",
                    "dataPlaneStatus": {"active": "true"},
                },
                "CONNECTION_RELEASED",
                id="released-active-dataplane",
            ),
            pytest.param(
                {
                    "lifecycleState": "Created",
                    "reservationState": "ReserveStart",
                    "provisionState": "Released",
                    "dataPlaneStatus": {"active": "false"},
                },
                "CONNECTION_RESERVE_COMMITTED",
                id="released-inactive-dataplane",
            ),
        ],
    )
    def test_mapping(self, nsi_states, expected):
        assert to_aura_connection_state(nsi_states) == expected


class TestReservationButtons:
    """Test that reservation_buttons renders correct buttons per state."""

    @pytest.mark.parametrize(
        "state,expected_buttons,absent_buttons",
        [
            pytest.param(
                "CONNECTION_ACTIVE",
                ["Release", "Verify"],
                ["Provision", "Reserve Again", "Terminate"],
                id="active-state",
            ),
            pytest.param(
                "CONNECTION_RESERVE_COMMITTED",
                ["Provision", "Terminate", "Verify"],
                ["Release", "Reserve Again"],
                id="committed-state",
            ),
            pytest.param(
                "CONNECTION_RESERVE_FAILED",
                ["Reserve Again", "Terminate"],
                ["Release", "Provision", "Verify"],
                id="reserve-failed-state",
            ),
            pytest.param(
                "CONNECTION_TERMINATED",
                ["Reserve Again", "Verify"],
                ["Release", "Provision", "Terminate"],
                id="terminated-state",
            ),
            pytest.param(
                "CONNECTION_PROVISIONED",
                ["Terminate"],
                ["Release", "Provision", "Reserve Again", "Verify"],
                id="provisioned-state",
            ),
            pytest.param(
                "CONNECTION_NEW",
                [],
                ["Release", "Provision", "Reserve Again", "Terminate", "Verify"],
                id="new-state",
            ),
            pytest.param(
                "CONNECTION_RESERVE_TIMEOUT",
                ["Terminate", "Verify"],
                ["Release", "Provision", "Reserve Again"],
                id="timeout-state",
            ),
            pytest.param(
                "CONNECTION_FAILED",
                ["Terminate", "Verify"],
                ["Release", "Provision", "Reserve Again"],
                id="failed-state",
            ),
            pytest.param(
                "CONNECTION_RELEASING",
                ["Verify"],
                ["Release", "Provision", "Reserve Again", "Terminate"],
                id="releasing-state",
            ),
            pytest.param(
                "CONNECTION_RESERVE_CHECKING",
                ["Verify"],
                ["Release", "Provision", "Reserve Again", "Terminate"],
                id="checking-state",
            ),
        ],
    )
    def test_buttons_per_state(self, state, expected_buttons, absent_buttons, reservation_factory):
        from aura.frontend.util import reservation_buttons

        reservation = reservation_factory(state=state)
        div = reservation_buttons(reservation)

        # Flatten all text from buttons in the div
        button_texts = []
        for component in div.components:
            if hasattr(component, "text"):
                button_texts.append(component.text)

        for expected in expected_buttons:
            assert expected in button_texts, f"Expected button '{expected}' not found in state {state}"

        for absent in absent_buttons:
            assert absent not in button_texts, f"Unexpected button '{absent}' found in state {state}"
