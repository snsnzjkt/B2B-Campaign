from unittest.mock import patch

import dns.exception

from app.core.email_verify import verify_email


def test_verify_email_valid_with_mx():
    with patch("app.core.email_verify.dns.resolver.resolve", return_value=["mx1.example.com"]):
        assert verify_email("person@example.com") is True


def test_verify_email_no_mx_record():
    with patch("app.core.email_verify.dns.resolver.resolve", side_effect=dns.exception.DNSException()):
        assert verify_email("person@example.com") is False


def test_verify_email_malformed_address():
    assert verify_email("not-an-email") is False
