import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest
from click.testing import CliRunner

import autounsubscriber.MailAutoUnsubscribe

LOCAL_IMAP_EMAIL = "address@example.org"
LOCAL_IMAP_PASSWORD = "pass"
LOCAL_IMAP_SERVER = "localhost"
LOCAL_IMAP_PORT = 993

LOCAL_SMTP_SERVER = "localhost"
LOCAL_SMTP_PORT = 25

logging.basicConfig(level=logging.DEBUG)


def imap_helper_cleanup_all_messages() -> None:
    with autounsubscriber.MailAutoUnsubscribe.login(
        LOCAL_IMAP_EMAIL,
        LOCAL_IMAP_PASSWORD,
        LOCAL_IMAP_SERVER,
        LOCAL_IMAP_PORT,
        tls=True,
        tls_certificate_validation=False,
    ) as imap_session:
        imap_session.select_folder("INBOX")
        uids = imap_session.search("ALL")
        if uids:
            imap_session.delete_messages(uids)
        imap_session.expunge()
        assert len(imap_session.search("ALL")) == 0


def imap_helper_count_messages() -> int:
    with autounsubscriber.MailAutoUnsubscribe.login(
        LOCAL_IMAP_EMAIL,
        LOCAL_IMAP_PASSWORD,
        LOCAL_IMAP_SERVER,
        LOCAL_IMAP_PORT,
        tls=True,
        tls_certificate_validation=False,
    ) as imap_session:
        imap_session.select_folder("INBOX")
        return len(imap_session.search("ALL"))


@pytest.fixture(autouse=True)
def run_before_and_after_tests_cleanup_inbox():
    """Fixture to execute asserts before and after a test is run"""
    # Setup: fill with any logic you want
    imap_helper_cleanup_all_messages()

    yield  # this is where the testing happens

    # Teardown : fill with any logic you want
    imap_helper_cleanup_all_messages()


def insert_some_mails_with_advertisement():
    old_message_count = imap_helper_count_messages()

    subject = "Hello World"
    html_content = """\
    <html>
    <body>
        <p>Hi,<br>
        This is a test email.
        </p>
    </body>
    </html>
    """

    send_email(
        LOCAL_SMTP_SERVER,
        LOCAL_SMTP_PORT,
        "test@test.de",
        LOCAL_IMAP_EMAIL,
        subject,
        html_content,
    )

    new_message_count = imap_helper_count_messages()

    assert new_message_count == (old_message_count + 1)


def send_email(
    smtp_server: str,
    port: int,
    sender_email: str,
    receiver_email: str,
    subject: str,
    html_content: str,
) -> None:
    # Setup the MIME
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = receiver_email

    # Add HTML content to the message
    part = MIMEText(html_content, "html")
    message.attach(part)

    # Use smtplib to send the email
    with smtplib.SMTP(smtp_server, port) as smtp_client:
        smtp_client.sendmail(sender_email, receiver_email, message.as_string())


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
            str(LOCAL_IMAP_PORT),
            "--tls",
            "--no-tls-certificate-validation",
        ],
    )

    assert result.exit_code == 0
    assert LOCAL_IMAP_EMAIL in result.output
    assert LOCAL_IMAP_PASSWORD not in result.output
    assert LOCAL_IMAP_SERVER in result.output
    assert str(LOCAL_IMAP_PORT) in result.output
    assert "TLS: True" in result.output
    assert "TLS-CERTIFICATE-VALIDATION: False" in result.output
    assert "found this data:" in result.output


def test_finding_advertisements():
    insert_some_mails_with_advertisement()

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
            str(LOCAL_IMAP_PORT),
            "--tls",
            "--no-tls-certificate-validation",
        ],
    )

    assert result.exit_code == 0
    assert "found this data:" in result.output
