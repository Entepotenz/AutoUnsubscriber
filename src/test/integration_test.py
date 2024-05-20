import pytest
from click.testing import CliRunner

import autounsubscriber.MailAutoUnsubscribe

LOCAL_IMAP_EMAIL = "address@example.org"
LOCAL_IMAP_PASSWORD = "pass"
LOCAL_IMAP_SERVER = "host.docker.internal"
LOCAL_IMAP_PORT = "993"


@pytest.fixture(autouse=True)
def run_before_and_after_tests():
    """Fixture to execute asserts before and after a test is run"""
    # Setup: fill with any logic you want
    print("hello")

    yield  # this is where the testing happens

    # Teardown : fill with any logic you want
    print("world")


def test_empty_mailbox():
    runner = CliRunner()
    result = runner.invoke(
        autounsubscriber.MailAutoUnsubscribe.main,
        [
            "--email",
            LOCAL_IMAP_EMAIL,
            "--password",
            LOCAL_IMAP_PASSWORD,
            "--imap-server",
            LOCAL_IMAP_SERVER,
            "--port",
            LOCAL_IMAP_PORT,
            "--tls",
            "--no-tls-certificate-validation",
        ],
    )

    assert result.exit_code == 0
    assert LOCAL_IMAP_EMAIL in result.output
    assert LOCAL_IMAP_PASSWORD not in result.output
    assert LOCAL_IMAP_SERVER in result.output
    assert LOCAL_IMAP_PORT in result.output
    assert "TLS: True" in result.output
    assert "TLS-CERTIFICATE-VALIDATION: False" in result.output
    assert "found this data:" in result.output
