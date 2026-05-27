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

"""Tests for aura.nsi: XML generation, parsing, and content type validation."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from aura.nsi import (
    acknowledgement_template,
    content_type_is_valid_soap,
    generate_acknowledgement_xml,
    generate_provision_xml,
    generate_query_recursive_xml,
    generate_query_summary_sync_xml,
    generate_release_xml,
    generate_reserve_abort_xml,
    generate_reserve_commit_xml,
    generate_reserve_xml,
    generate_reserve_timeout_ack_xml,
    generate_terminate_xml,
    nsi_soap_parse_correlationid_reply,
    nsi_soap_parse_reserve_reply,
    nsi_util_element_to_dict,
    nsi_xml_to_dict,
    provision_template,
    query_recursive_template,
    query_summary_sync_template,
    release_template,
    reserve_abort_template,
    reserve_commit_template,
    reserve_template,
    reserve_timeout_ack_template,
    terminate_template,
)


class TestContentTypeIsValidSoap:
    @pytest.mark.parametrize(
        "content_type,expected",
        [
            pytest.param("application/xml", True, id="application-xml"),
            pytest.param("APPLICATION/XML", True, id="application-xml-upper"),
            pytest.param("text/xml", True, id="text-xml"),
            pytest.param("text/xml;charset=utf-8", True, id="text-xml-charset"),
            pytest.param("text/xml; charset=UTF-8", True, id="text-xml-charset-space"),
            pytest.param("TEXT/XML", True, id="text-xml-upper"),
            pytest.param("application/json", False, id="json"),
            pytest.param("text/html", False, id="html"),
            pytest.param("application/soap+xml", False, id="soap-xml"),
        ],
    )
    def test_content_type_validation(self, content_type, expected):
        assert content_type_is_valid_soap(content_type) == expected


class TestGenerateReserveXml:
    def test_all_placeholders_replaced(self):
        correlation_id = uuid4()
        global_res_id = uuid4()
        result = generate_reserve_xml(
            reserve_template,
            correlation_id,
            "http://reply.example/callback",
            "Test Connection",
            global_res_id,
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 12, 31, tzinfo=timezone.utc),
            "urn:ogf:network:example:port1?vlan=100",
            "urn:ogf:network:example:port2?vlan=200",
            "urn:ogf:network:example:nsa:provider",
        )
        xml_str = result.decode()
        assert str(correlation_id) in xml_str
        assert "Test Connection" in xml_str
        assert str(global_res_id) in xml_str
        assert "urn:ogf:network:example:port1?vlan=100" in xml_str
        assert "urn:ogf:network:example:port2?vlan=200" in xml_str
        assert "urn:ogf:network:example:nsa:provider" in xml_str
        # No unreplaced placeholders
        assert "#CORRELATION-ID#" not in xml_str
        assert "#SOURCE-STP#" not in xml_str
        assert "#DEST-STP#" not in xml_str
        assert "#PROVIDER-NSA-ID#" not in xml_str
        assert "#REPLY-TO-URL#" not in xml_str

    def test_returns_bytes(self):
        result = generate_reserve_xml(
            reserve_template,
            uuid4(),
            "http://example.com/cb",
            "desc",
            uuid4(),
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 12, 31, tzinfo=timezone.utc),
            "urn:src",
            "urn:dst",
            "provider-nsa",
        )
        assert isinstance(result, bytes)


class TestGenerateSimpleXml:
    """Test the XML generators that share the (template, correlation, reply_to, connection_id, provider) signature."""

    @pytest.mark.parametrize(
        "generator,template",
        [
            pytest.param(generate_reserve_commit_xml, reserve_commit_template, id="reserve-commit"),
            pytest.param(generate_reserve_abort_xml, reserve_abort_template, id="reserve-abort"),
            pytest.param(generate_provision_xml, provision_template, id="provision"),
            pytest.param(generate_terminate_xml, terminate_template, id="terminate"),
            pytest.param(generate_release_xml, release_template, id="release"),
            pytest.param(generate_reserve_timeout_ack_xml, reserve_timeout_ack_template, id="reserve-timeout-ack"),
            pytest.param(generate_query_recursive_xml, query_recursive_template, id="query-recursive"),
        ],
    )
    def test_placeholders_replaced(self, generator, template):
        corr_id = uuid4()
        conn_id = "test-connection-id-123"
        result = generator(template, corr_id, "http://reply.example/cb", conn_id, "provider-nsa-id")
        xml_str = result.decode()
        assert "#CORRELATION-ID#" not in xml_str
        assert "#CONNECTION-ID#" not in xml_str
        assert "#PROVIDER-NSA-ID#" not in xml_str
        assert "#REPLY-TO-URL#" not in xml_str
        assert str(corr_id) in xml_str
        assert conn_id in xml_str

    @pytest.mark.parametrize(
        "generator,template",
        [
            pytest.param(generate_reserve_commit_xml, reserve_commit_template, id="reserve-commit"),
            pytest.param(generate_reserve_abort_xml, reserve_abort_template, id="reserve-abort"),
            pytest.param(generate_provision_xml, provision_template, id="provision"),
            pytest.param(generate_terminate_xml, terminate_template, id="terminate"),
            pytest.param(generate_release_xml, release_template, id="release"),
            pytest.param(generate_reserve_timeout_ack_xml, reserve_timeout_ack_template, id="reserve-timeout-ack"),
            pytest.param(generate_query_recursive_xml, query_recursive_template, id="query-recursive"),
        ],
    )
    def test_returns_bytes(self, generator, template):
        result = generator(template, uuid4(), "http://example.com/cb", "conn-id", "prov-nsa")
        assert isinstance(result, bytes)


class TestGenerateQuerySummarySyncXml:
    """query_summary_sync has a different signature: no reply_to_url parameter."""

    def test_placeholders_replaced(self):
        corr_id = uuid4()
        conn_id = "test-conn-id"
        result = generate_query_summary_sync_xml(query_summary_sync_template, corr_id, conn_id, "provider-nsa")
        xml_str = result.decode()
        assert "#CORRELATION-ID#" not in xml_str
        assert "#CONNECTION-ID#" not in xml_str
        assert "#PROVIDER-NSA-ID#" not in xml_str
        assert str(corr_id) in xml_str
        assert conn_id in xml_str

    def test_returns_bytes(self):
        result = generate_query_summary_sync_xml(query_summary_sync_template, uuid4(), "conn-id", "prov-nsa")
        assert isinstance(result, bytes)


class TestGenerateAcknowledgementXml:
    def test_placeholders_replaced(self):
        corr_id = uuid4()
        result = generate_acknowledgement_xml(acknowledgement_template, corr_id, "provider-nsa-id")
        xml_str = result.decode()
        assert "#CORRELATION-ID#" not in xml_str
        assert "#PROVIDER-NSA-ID#" not in xml_str
        assert str(corr_id) in xml_str
        assert "provider-nsa-id" in xml_str

    def test_returns_bytes(self):
        result = generate_acknowledgement_xml(acknowledgement_template, uuid4(), "prov")
        assert isinstance(result, bytes)


class TestNsiXmlToDict:
    def test_simple_soap_envelope(self):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Header>
                <nsiHeader xmlns="http://schemas.ogf.org/nsi/2013/12/framework/headers">
                    <correlationId>4f0a4f6b-1187-4670-b451-bb8005105ba5</correlationId>
                    <providerNSA>urn:ogf:network:example:nsa</providerNSA>
                </nsiHeader>
            </soap:Header>
            <soap:Body>
                <connectionId>1153d8ed-f97b-4f01-b529-af8080980ea9</connectionId>
            </soap:Body>
        </soap:Envelope>"""
        result = nsi_xml_to_dict(xml)
        assert "Header" in result
        assert "Body" in result
        assert isinstance(result["Body"]["connectionId"], UUID)
        assert str(result["Body"]["connectionId"]) == "1153d8ed-f97b-4f01-b529-af8080980ea9"

    def test_nested_elements(self):
        xml = b"""<root>
            <parent>
                <child>value</child>
            </parent>
        </root>"""
        result = nsi_xml_to_dict(xml)
        assert result["parent"]["child"] == "value"

    def test_duplicate_keys_become_list(self):
        xml = b"""<root>
            <item>first</item>
            <item>second</item>
        </root>"""
        result = nsi_xml_to_dict(xml)
        assert result["item"] == ["first", "second"]

    def test_attributes_included(self):
        xml = b"""<root>
            <element attr1="val1">text</element>
        </root>"""
        result = nsi_xml_to_dict(xml)
        assert result["element"] == "text"


class TestNsiUtilElementToDict:
    def test_with_attributes(self):
        from lxml import etree

        xml = b'<root type="test" id="1"><child>value</child></root>'
        node = etree.fromstring(xml)
        result = nsi_util_element_to_dict(node, attributes=True)
        assert result["type"] == "test"
        assert result["id"] == "1"
        assert result["child"] == "value"

    def test_without_attributes(self):
        from lxml import etree

        xml = b'<root type="test"><child>value</child></root>'
        node = etree.fromstring(xml)
        result = nsi_util_element_to_dict(node, attributes=False)
        assert "type" not in result
        assert result["child"] == "value"

    def test_uuid_parsing(self):
        from lxml import etree

        xml = b"<root><connectionId>4f0a4f6b-1187-4670-b451-bb8005105ba5</connectionId></root>"
        node = etree.fromstring(xml)
        result = nsi_util_element_to_dict(node)
        assert isinstance(result["connectionId"], UUID)

    def test_datetime_parsing(self):
        from lxml import etree

        xml = b"<root><startTime>2025-01-01T00:00:00+00:00</startTime></root>"
        node = etree.fromstring(xml)
        result = nsi_util_element_to_dict(node)
        assert isinstance(result["startTime"], datetime)


class TestNsiSoapParseReserveReply:
    def test_successful_reply(self):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Header>
                <correlationId>urn:uuid:abc-123</correlationId>
            </soap:Header>
            <soap:Body>
                <connectionId>def-456-789-abc-def012345</connectionId>
            </soap:Body>
        </soap:Envelope>"""
        result = nsi_soap_parse_reserve_reply(xml)
        assert result["correlationId"] == "urn:uuid:abc-123"
        assert result["connectionId"] == "def-456-789-abc-def012345"
        assert result["faultstring"] is None

    def test_fault_reply(self):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Header>
                <correlationId>urn:uuid:abc-123</correlationId>
            </soap:Header>
            <soap:Body>
                <connectionId>def-456</connectionId>
                <faultstring>Some SOAP error</faultstring>
            </soap:Body>
        </soap:Envelope>"""
        result = nsi_soap_parse_reserve_reply(xml)
        assert result["faultstring"] == "Some SOAP error"


class TestNsiXmlToDictEdgeCases:
    def test_invalid_xml_raises(self):
        from lxml import etree

        with pytest.raises(etree.XMLSyntaxError):
            nsi_xml_to_dict(b"<unclosed>")

    def test_three_duplicate_keys_become_list(self):
        xml = b"""<root>
            <item>first</item>
            <item>second</item>
            <item>third</item>
        </root>"""
        result = nsi_xml_to_dict(xml)
        assert result["item"] == ["first", "second", "third"]


class TestNsiSoapParseCorrelationidReply:
    def test_successful_reply(self):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Header>
                <correlationId>urn:uuid:abc-123</correlationId>
            </soap:Header>
            <soap:Body></soap:Body>
        </soap:Envelope>"""
        result = nsi_soap_parse_correlationid_reply(xml)
        assert result["correlationId"] == "urn:uuid:abc-123"
        assert result["faultstring"] is None

    def test_fault_reply(self):
        xml = b"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Header>
                <correlationId>urn:uuid:abc-123</correlationId>
            </soap:Header>
            <soap:Body>
                <faultstring>Error occurred</faultstring>
            </soap:Body>
        </soap:Envelope>"""
        result = nsi_soap_parse_correlationid_reply(xml)
        assert result["faultstring"] == "Error occurred"
