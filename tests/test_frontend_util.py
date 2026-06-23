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

"""Tests for amiss.frontend.util: reservation_buttons (read-only)."""

import pytest


class TestReservationButtons:
    """reservation_buttons is read-only now: always just Back + Log, no action buttons."""

    @pytest.mark.parametrize(
        "state",
        ["CONNECTION_NEW", "CONNECTION_ACTIVE", "CONNECTION_RESERVE_COMMITTED", "CONNECTION_TERMINATED"],
    )
    def test_only_back_and_log(self, state, reservation_factory):
        from amiss.frontend.util import reservation_buttons

        div = reservation_buttons(reservation_factory(state=state))

        button_texts = [component.text for component in div.components if hasattr(component, "text")]
        assert button_texts == ["Back", "Log"]
        for action in ("Release", "Provision", "Reserve Again", "Terminate", "Verify"):
            assert action not in button_texts
