"""Tests for AD retry telemetry capture and reporting (issue #21)."""

import unittest
from unittest.mock import MagicMock, patch

from ldap3.core.exceptions import (
    LDAPCommunicationError,
    LDAPSessionTerminatedByServerError,
)

from python_apis.apis.ad_api import (
    ADConnection,
    AD_READ_RETRY_POLICY,
    AD_WRITE_RETRY_POLICY,
    RetryTelemetry,
)
from python_apis.models.ad_responses import ADOperationEnvelope
from python_apis.services.compatibility_mode import (
    finalize_ad_read_response,
    finalize_ad_write_response,
)


class TestApiLayerRetryTelemetry(unittest.TestCase):
    """Validate telemetry recorded by the auto-reconnect decorator."""

    def setUp(self):
        self.servers = ['ldap://server1', 'ldap://server2']
        self.search_base = 'dc=example,dc=com'

        patcher = patch('python_apis.apis.ad_api.Connection')
        self.mock_connection_cls = patcher.start()
        self.mock_connection = MagicMock()
        self.mock_connection.bind.return_value = True
        self.mock_connection_cls.return_value = self.mock_connection
        self.addCleanup(patcher.stop)

    def test_no_retry_success_records_read_telemetry(self):
        conn = ADConnection(self.servers, self.search_base)
        mock_result = [{'attributes': {'cn': 'John Doe'}}]
        self.mock_connection.extend.standard.paged_search.return_value = iter(mock_result)

        conn.search('(objectClass=user)', ['cn'])

        telemetry = conn.last_retry_telemetry
        self.assertIsNotNone(telemetry)
        self.assertEqual(telemetry.operation_kind, 'read')
        self.assertEqual(telemetry.retry_count, 0)
        self.assertFalse(telemetry.retried)
        self.assertFalse(telemetry.would_retry)
        self.assertFalse(telemetry.recovered)
        self.assertEqual(telemetry.policy, AD_READ_RETRY_POLICY)

    def test_recover_after_retry_records_write_telemetry(self):
        conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.modify.side_effect = [
            LDAPSessionTerminatedByServerError('boom'),
            True,
        ]
        self.mock_connection.result = {'description': 'success'}

        with patch.object(conn, 'rebind') as mock_rebind:
            response = conn.modify('CN=x,dc=example,dc=com', [('title', 'Dev')])

        mock_rebind.assert_called_once()
        self.assertTrue(response['success'])
        telemetry = conn.last_retry_telemetry
        self.assertEqual(telemetry.operation_kind, 'write')
        self.assertEqual(telemetry.retry_count, 1)
        self.assertTrue(telemetry.retried)
        self.assertTrue(telemetry.would_retry)
        self.assertTrue(telemetry.recovered)
        self.assertEqual(telemetry.policy, AD_WRITE_RETRY_POLICY)

    def test_non_recoverable_exception_propagates_without_retry(self):
        conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.modify.side_effect = ValueError('bad input')

        with patch.object(conn, 'rebind') as mock_rebind:
            with self.assertRaises(ValueError):
                conn.modify('CN=x,dc=example,dc=com', [('title', 'Dev')])

        mock_rebind.assert_not_called()
        telemetry = conn.last_retry_telemetry
        self.assertEqual(telemetry.operation_kind, 'write')
        self.assertEqual(telemetry.retry_count, 0)
        self.assertFalse(telemetry.retried)
        self.assertFalse(telemetry.recovered)

    def test_failed_retry_records_attempt_without_recovery(self):
        conn = ADConnection(self.servers, self.search_base)
        self.mock_connection.modify.side_effect = [
            LDAPCommunicationError('first'),
            LDAPCommunicationError('second'),
        ]

        with patch.object(conn, 'rebind') as mock_rebind:
            with self.assertRaises(LDAPCommunicationError):
                conn.modify('CN=x,dc=example,dc=com', [('title', 'Dev')])

        mock_rebind.assert_called_once()
        telemetry = conn.last_retry_telemetry
        self.assertEqual(telemetry.retry_count, 1)
        self.assertTrue(telemetry.retried)
        self.assertTrue(telemetry.would_retry)
        self.assertFalse(telemetry.recovered)


class TestEnvelopeRetryFields(unittest.TestCase):
    """Validate retry fields surface on the envelope across compatibility modes."""

    def _build_envelope(self):
        return ADOperationEnvelope.from_operation(
            operation_kind='write',
            success=True,
            ldap_result={'description': 'success'},
            retry_count=1,
            retried=True,
            would_retry=True,
            retry_policy=AD_WRITE_RETRY_POLICY,
        )

    def test_retry_fields_present_in_mixed_mode(self):
        payload = self._build_envelope().to_response('mixed')

        self.assertEqual(payload['retry_count'], 1)
        self.assertTrue(payload['retried'])
        self.assertTrue(payload['would_retry'])
        self.assertTrue(payload['did_retry'])
        self.assertEqual(payload['retry_policy'], AD_WRITE_RETRY_POLICY)

    def test_retry_fields_present_in_strict_mode(self):
        payload = self._build_envelope().to_response('strict')

        self.assertEqual(payload['retry_count'], 1)
        self.assertTrue(payload['did_retry'])
        self.assertEqual(payload['retry_policy'], AD_WRITE_RETRY_POLICY)
        self.assertNotIn('result', payload)
        self.assertNotIn('message', payload)

    def test_did_retry_mirrors_retried(self):
        envelope = ADOperationEnvelope.from_operation(
            operation_kind='read',
            success=True,
            retried=False,
        )

        self.assertFalse(envelope.did_retry)


class TestWriteResponseRetryIntegration(unittest.TestCase):
    """Validate finalize_ad_write_response threads retry telemetry."""

    def setUp(self):
        self.telemetry = RetryTelemetry(
            operation_kind='write',
            retry_count=1,
            retried=True,
            would_retry=True,
            recovered=True,
            policy=AD_WRITE_RETRY_POLICY,
        )

    def test_legacy_mode_ignores_telemetry(self):
        legacy = {'success': True, 'result': 'ok'}

        payload = finalize_ad_write_response(
            legacy,
            effective_mode='legacy',
            retry_telemetry=self.telemetry,
        )

        self.assertEqual(payload, legacy)

    def test_mixed_mode_includes_telemetry(self):
        payload = finalize_ad_write_response(
            {'success': True, 'result': 'ok'},
            effective_mode='mixed',
            retry_telemetry=self.telemetry,
        )

        self.assertEqual(payload['retry_count'], 1)
        self.assertTrue(payload['did_retry'])
        self.assertEqual(payload['retry_policy']['strategy'], 'rebind_once')

    def test_absent_telemetry_yields_defaults(self):
        payload = finalize_ad_write_response(
            {'success': True, 'result': 'ok'},
            effective_mode='mixed',
        )

        self.assertEqual(payload['retry_count'], 0)
        self.assertFalse(payload['retried'])
        self.assertFalse(payload['would_retry'])
        self.assertIsNone(payload['retry_policy'])


class TestReadResponseRetryIntegration(unittest.TestCase):
    """Validate finalize_ad_read_response builds opt-in read envelopes."""

    def setUp(self):
        self.telemetry = RetryTelemetry(
            operation_kind='read',
            retry_count=1,
            retried=True,
            would_retry=True,
            recovered=True,
            policy=AD_READ_RETRY_POLICY,
        )

    def test_legacy_mode_returns_raw_result(self):
        result = ['a', 'b']

        returned = finalize_ad_read_response(
            result,
            effective_mode='legacy',
            retry_telemetry=self.telemetry,
        )

        self.assertIs(returned, result)

    def test_mixed_mode_builds_read_envelope(self):
        payload = finalize_ad_read_response(
            ['a', 'b'],
            effective_mode='mixed',
            retry_telemetry=self.telemetry,
        )

        self.assertEqual(payload['operation_kind'], 'read')
        self.assertEqual(payload['result'], ['a', 'b'])
        self.assertEqual(payload['retry_count'], 1)
        self.assertTrue(payload['did_retry'])
        self.assertEqual(payload['retry_policy'], AD_READ_RETRY_POLICY)

    def test_strict_mode_omits_legacy_mirrors(self):
        payload = finalize_ad_read_response(
            ['a', 'b'],
            effective_mode='strict',
        )

        self.assertEqual(payload['operation_kind'], 'read')
        self.assertNotIn('result', payload)
        self.assertNotIn('message', payload)
        self.assertEqual(payload['retry_count'], 0)

    def test_failure_defaults_success_from_exception(self):
        payload = finalize_ad_read_response(
            [],
            effective_mode='mixed',
            exception=LDAPCommunicationError('down'),
        )

        self.assertFalse(payload['success'])
        self.assertEqual(payload['exception_type'], 'LDAPCommunicationError')


if __name__ == '__main__':
    unittest.main()
