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

"""Tests for aura.model: STP properties, Reservation validation, and type constraints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from aura.model import STP, Reservation


def _reservation_data(**overrides):
    """Return a valid Reservation data dict with optional overrides."""
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
    defaults.update(overrides)
    return defaults


class TestSTPOrganisationId:
    @pytest.mark.parametrize(
        "stp_id,expected",
        [
            pytest.param(
                "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
                "surf.ana.dlp.surfnet.nl:2024",
                id="surf",
            ),
            pytest.param(
                "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1",
                "moxy.ana.dlp.surfnet.nl:2024",
                id="moxy",
            ),
        ],
    )
    def test_organisationId(self, stp_id, expected, stp_factory):
        stp = stp_factory(stpId=stp_id)
        assert stp.organisationId == expected


class TestSTPNetworkId:
    @pytest.mark.parametrize(
        "stp_id,expected",
        [
            pytest.param(
                "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
                "ana-surf",
                id="surf",
            ),
            pytest.param(
                "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1",
                "ana-moxy",
                id="moxy",
            ),
        ],
    )
    def test_networkId(self, stp_id, expected, stp_factory):
        stp = stp_factory(stpId=stp_id)
        assert stp.networkId == expected


class TestSTPLocalId:
    @pytest.mark.parametrize(
        "stp_id,expected",
        [
            pytest.param(
                "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
                "university-1",
                id="simple-local",
            ),
            pytest.param(
                "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1",
                "hpc-1",
                id="hpc",
            ),
            pytest.param(
                "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1:in",
                "link-to-surf-1:in",
                id="multi-colon-local",
            ),
        ],
    )
    def test_localId(self, stp_id, expected, stp_factory):
        stp = stp_factory(stpId=stp_id)
        assert stp.localId == expected


class TestSTPUrn:
    @pytest.mark.parametrize(
        "stp_id,expected",
        [
            pytest.param(
                "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
                "urn:ogf:network:urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
                id="full-urn-base",
            ),
            pytest.param(
                "surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
                "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
                id="stripped-urn-base",
            ),
        ],
    )
    def test_urn_base(self, stp_id, expected, stp_factory):
        stp = stp_factory(stpId=stp_id)
        assert stp.urn_base == expected

    @pytest.mark.parametrize(
        "stp_id,vlan_range,expected",
        [
            pytest.param(
                "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
                "100-200",
                "urn:ogf:network:urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1?vlan=100-200",
                id="full-urn-with-vlan",
            ),
            pytest.param(
                "surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1",
                "100-200",
                "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1?vlan=100-200",
                id="stripped-urn-with-vlan",
            ),
        ],
    )
    def test_urn(self, stp_id, vlan_range, expected, stp_factory):
        stp = stp_factory(stpId=stp_id, vlanRange=vlan_range)
        assert stp.urn == expected


class TestSTPPropertiesWithStrippedStpId:
    """Stripped stpIds have fewer colon-separated parts and will raise ValueError."""

    def test_stripped_stpid_raises_on_properties(self, stp_factory):
        stp = stp_factory(stpId="surf.ana.dlp.surfnet.nl:2024:ana-surf:university-1")
        with pytest.raises(ValueError, match="not enough values to unpack"):
            _ = stp.organisationId


class TestReservationVlanValidation:
    """SQLModel doesn't enforce Annotated constraints at __init__ time.

    Use model_validate to trigger Pydantic validation of Vlan (Ge(2), Le(4094))
    and Bandwidth (Gt(0)) constraints.
    """

    @pytest.mark.parametrize(
        "vlan,should_pass",
        [
            pytest.param(1, False, id="below-minimum"),
            pytest.param(2, True, id="minimum-valid"),
            pytest.param(100, True, id="normal-value"),
            pytest.param(4094, True, id="maximum-valid"),
            pytest.param(4095, False, id="above-maximum"),
        ],
    )
    def test_source_vlan_boundaries(self, vlan, should_pass):
        data = _reservation_data(sourceVlan=vlan)
        if should_pass:
            reservation = Reservation.model_validate(data)
            assert reservation.sourceVlan == vlan
        else:
            with pytest.raises(ValidationError):
                Reservation.model_validate(data)

    @pytest.mark.parametrize(
        "vlan,should_pass",
        [
            pytest.param(1, False, id="below-minimum"),
            pytest.param(2, True, id="minimum-valid"),
            pytest.param(4094, True, id="maximum-valid"),
            pytest.param(4095, False, id="above-maximum"),
        ],
    )
    def test_dest_vlan_boundaries(self, vlan, should_pass):
        data = _reservation_data(destVlan=vlan)
        if should_pass:
            reservation = Reservation.model_validate(data)
            assert reservation.destVlan == vlan
        else:
            with pytest.raises(ValidationError):
                Reservation.model_validate(data)


class TestReservationBandwidthValidation:
    @pytest.mark.parametrize(
        "bandwidth,should_pass",
        [
            pytest.param(0, False, id="zero-invalid"),
            pytest.param(-1, False, id="negative-invalid"),
            pytest.param(1, True, id="minimum-valid"),
            pytest.param(100000, True, id="large-value"),
        ],
    )
    def test_bandwidth_boundaries(self, bandwidth, should_pass):
        data = _reservation_data(bandwidth=bandwidth)
        if should_pass:
            reservation = Reservation.model_validate(data)
            assert reservation.bandwidth == bandwidth
        else:
            with pytest.raises(ValidationError):
                Reservation.model_validate(data)
