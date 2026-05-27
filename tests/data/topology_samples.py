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

"""Sample topology data for DDS tests.

Extracted from aura/dds.py __main__ block.
"""

MOXY_TOPOLOGY = {
    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy",
    "version": "2025-03-19T07:38:58Z",
    "name": "ANA MOXY topology",
    "Lifetime": {"start": "2025-03-19T07:38:58Z", "end": "2025-03-26T07:38:58Z"},
    "BidirectionalPort": [
        {
            "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1",
            "name": "High Performance Cluster in Canada",
            "PortGroup": [
                {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1:in"},
                {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1:out"},
            ],
        },
        {
            "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1",
            "name": "Research institute in Canada",
            "PortGroup": [
                {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1:in"},
                {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1:out"},
            ],
        },
        {
            "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1",
            "name": "ANA link 1 MOXY towards SURF",
            "PortGroup": [
                {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1:in"},
                {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1:out"},
            ],
        },
        {
            "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-2",
            "name": "ANA link 2 MOXY towards SURF",
            "PortGroup": [
                {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-2:in"},
                {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-2:out"},
            ],
        },
    ],
    "serviceDefinition": {
        "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:sd:EVTS.A-GOLE",
        "name": "GLIF Automated GOLE Ethernet VLAN Transfer Service",
        "serviceType": "http://services.ogf.org/nsi/2013/12/descriptions/EVTS.A-GOLE",
    },
    "Relation": [
        {
            "type": "http://schemas.ogf.org/nml/2013/05/base#hasService",
            "SwitchingService": {
                "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
                "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:switch:EVTS.A-GOLE",
                "labelSwapping": "true",
                "labelType": "http://schemas.ogf.org/nml/2012/10/ethernet#vlan",
                "Relation": [
                    {
                        "type": "http://schemas.ogf.org/nml/2013/05/base#hasInboundPort",
                        "PortGroup": [
                            {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1:in"},
                            {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1:in"},
                            {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1:in"},
                            {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-2:in"},
                        ],
                    },
                    {
                        "type": "http://schemas.ogf.org/nml/2013/05/base#hasOutboundPort",
                        "PortGroup": [
                            {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1:out"},
                            {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1:out"},
                            {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1:out"},
                            {"id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-2:out"},
                        ],
                    },
                ],
                "serviceDefinition": {
                    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:sd:EVTS.A-GOLE"
                },
            },
        },
        {
            "type": "http://schemas.ogf.org/nml/2013/05/base#hasInboundPort",
            "PortGroup": [
                {
                    "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1:in",
                    "LabelGroup": "3762-3769",
                    "capacity": "10000000000",
                    "granularity": "1000000",
                    "minimumReservableCapacity": "1000000",
                    "maximumReservableCapacity": "10000000000",
                },
                {
                    "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1:in",
                    "LabelGroup": "147",
                    "capacity": "10000000000",
                    "granularity": "1000000",
                    "minimumReservableCapacity": "1000000",
                    "maximumReservableCapacity": "10000000000",
                },
                {
                    "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1:in",
                    "LabelGroup": "1330-1429",
                    "Relation": {
                        "type": "http://schemas.ogf.org/nml/2013/05/base#isAlias",
                        "PortGroup": {
                            "id": "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:ana-link-1:out"
                        },
                    },
                    "capacity": "100000000000",
                    "granularity": "1000000",
                    "minimumReservableCapacity": "1000000",
                    "maximumReservableCapacity": "100000000000",
                },
                {
                    "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-2:in",
                    "LabelGroup": "88-97",
                    "Relation": {
                        "type": "http://schemas.ogf.org/nml/2013/05/base#isAlias",
                        "PortGroup": {
                            "id": "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:ana-link-2:out"
                        },
                    },
                    "capacity": "100000000000",
                    "granularity": "1000000",
                    "minimumReservableCapacity": "1000000",
                    "maximumReservableCapacity": "100000000000",
                },
            ],
        },
        {
            "type": "http://schemas.ogf.org/nml/2013/05/base#hasOutboundPort",
            "PortGroup": [
                {
                    "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:hpc-1:out",
                    "LabelGroup": "3762-3769",
                    "capacity": "10000000000",
                    "granularity": "1000000",
                    "minimumReservableCapacity": "1000000",
                    "maximumReservableCapacity": "10000000000",
                },
                {
                    "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:research-1:out",
                    "LabelGroup": "147",
                    "capacity": "10000000000",
                    "granularity": "1000000",
                    "minimumReservableCapacity": "1000000",
                    "maximumReservableCapacity": "10000000000",
                },
                {
                    "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-1:out",
                    "LabelGroup": "1330-1429",
                    "Relation": {
                        "type": "http://schemas.ogf.org/nml/2013/05/base#isAlias",
                        "PortGroup": {
                            "id": "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:ana-link-1:in"
                        },
                    },
                    "capacity": "100000000000",
                    "granularity": "1000000",
                    "minimumReservableCapacity": "1000000",
                    "maximumReservableCapacity": "100000000000",
                },
                {
                    "encoding": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "id": "urn:ogf:network:moxy.ana.dlp.surfnet.nl:2024:ana-moxy:link-to-surf-2:out",
                    "LabelGroup": "88-97",
                    "Relation": {
                        "type": "http://schemas.ogf.org/nml/2013/05/base#isAlias",
                        "PortGroup": {
                            "id": "urn:ogf:network:surf.ana.dlp.surfnet.nl:2024:ana-surf:ana-link-2:in"
                        },
                    },
                    "capacity": "100000000000",
                    "granularity": "1000000",
                    "minimumReservableCapacity": "1000000",
                    "maximumReservableCapacity": "100000000000",
                },
            ],
        },
    ],
}


MINIMAL_TOPOLOGY = {
    "id": "urn:ogf:network:test:2024:net",
    "BidirectionalPort": [
        {
            "id": "urn:ogf:network:test:2024:net:port-1",
            "name": "Test port",
            "PortGroup": [
                {"id": "urn:ogf:network:test:2024:net:port-1:in"},
                {"id": "urn:ogf:network:test:2024:net:port-1:out"},
            ],
        },
    ],
    "Relation": [
        {
            "type": "http://schemas.ogf.org/nml/2013/05/base#hasInboundPort",
            "PortGroup": [
                {
                    "id": "urn:ogf:network:test:2024:net:port-1:in",
                    "LabelGroup": "100-200",
                },
            ],
        },
        {
            "type": "http://schemas.ogf.org/nml/2013/05/base#hasOutboundPort",
            "PortGroup": [
                {
                    "id": "urn:ogf:network:test:2024:net:port-1:out",
                    "LabelGroup": "100-200",
                },
            ],
        },
    ],
}
