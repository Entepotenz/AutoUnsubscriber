import logging
import typing
from datetime import datetime

import bs4
import click
import pyzmail
from dateutil import parser as dateutil_parser
from imapclient import imapclient
import ssl as ssl_lib

logging.basicConfig(level=logging.INFO)


@click.command()  # type: ignore
@click.option(  # type: ignore
    "--email", prompt="Your email address", help="Your email address", type=click.STRING
)
@click.option(  # type: ignore
    "--password",
    prompt="Your password",
    hide_input=True,
    help="Your password",
    type=click.STRING,
)
@click.option(  # type: ignore
    "--imap-server",
    prompt="IMAP server name",
    help="IMAP server name",
    type=click.STRING,
)
@click.option(  # type: ignore
    "--port",
    default=993,
    help="Port number for IMAP server",
    type=click.INT,
)
@click.option(  # type: ignore
    "--tls/--no-tls",
    default=True,
    help="Enable / Disable TLS for communication with IMAP server",
    type=click.BOOL,
)
@click.option(  # type: ignore
    "--tls-certificate-validation/--no-tls-certificate-validation",
    default=True,
    help="Enable / Disable TLS validation of server certificate",
    type=click.BOOL,
)
def main(
    email: str,
    password: str,
    imap_server: str,
    port: int,
    tls: bool,
    tls_certificate_validation: bool,
) -> None:
    click.echo("Email address: {}".format(email))
    click.echo("Password: {}".format("*" * len(password)))  # Masking password
    click.echo("IMAP server: {}".format(imap_server))
    click.echo("Port: {}".format(port))
    click.echo("TLS: {}".format(tls))
    click.echo("TLS-CERTIFICATE-VALIDATION: {}".format(tls_certificate_validation))

    detection_keywords = [
        "unsubscribe",
        "subscription",
        "optout",
        "abbestellen",
        "abmelden",
    ]

    with login(
        email, password, imap_server, port, tls, tls_certificate_validation
    ) as imap_session:
        data = get_mails_with_detected_keywords(imap_session, detection_keywords)

        data_grouped = group_by_mail_sender_name_and_sorted_by_date(data)

        for key, value in data_grouped.items():
            logging.info(f'{key} - {value[0]["from"][1]} - {value[0]["url"]}')


def login(
    email: str,
    password: str,
    imap_server: str,
    port: int,
    tls: bool,
    tls_certificate_validation: bool,
) -> imapclient.IMAPClient:
    try:
        ssl_context = None
        if not tls_certificate_validation:
            ssl_context = ssl_lib.SSLContext()
            ssl_context.verify_mode = ssl_lib.CERT_NONE
            ssl_context.check_hostname = False

        imap = imapclient.IMAPClient(
            imap_server, port=port, ssl=tls, timeout=30, ssl_context=ssl_context
        )
        imap.login(email, password)
        logging.info("Log in successful")
        return imap
    except imapclient.exceptions.IMAPClientError as error:
        logging.error("An error occurred while attempting to log in: {}", error)
    except Exception as error:
        logging.error("An error occurred while attempting to log in: {}", error)


def get_mails_with_detected_keywords(
    imap_session: imapclient.IMAPClient, detection_keywords: list[str]
) -> dict[int, dict[str, typing.Any]]:
    if not imap_session.folder_exists("INBOX"):
        logging.warning("'INBOX' folder does not exist!")
    logging.debug("%s", imap_session.list_folders())
    imap_session.select_folder("INBOX", readonly=True)

    is_imap_search_supported = is_imap_server_supporting_search_capability(imap_session)

    detection_results = {}
    merged_uid_list: list[int] = list()

    if is_imap_search_supported:
        for keyword in detection_keywords:
            messages = imap_session.search(["TEXT", keyword])
            detection_results[keyword] = messages

        for item in detection_results.values():
            merged_uid_list = list(set(item).union(set(merged_uid_list)))
    else:
        logging.warning(
            "IMAP server does not support 'search' -> falling back to downloading messages (this can take some time)"
        )
        all_uids_in_inbox = imap_session.search()
        merged_uid_list = list(set(all_uids_in_inbox))

    uids_with_details: dict[int, dict[str, typing.Any]] = {}

    chunk_size = 10
    chunks = [
        merged_uid_list[x : x + chunk_size]
        for x in range(0, len(merged_uid_list), chunk_size)
    ]

    for chunk in chunks:
        messages_raw = dict()
        try:
            messages_raw = imap_session.fetch(chunk, ["BODY[]"])
        except imapclient.exceptions.IMAPClientError as error:
            logging.warning(
                "encountered error while fetching uid: %s; error message: '%s'",
                ",".join(map(str, chunk)),
                error,
            )
            for uid in chunk:
                try:
                    messages_raw[uid] = imap_session.fetch([uid], ["BODY[]"])
                except imapclient.exceptions.IMAPClientError as error:
                    logging.error(
                        "encountered error while fetching uid: %d; we will SKIP this uid; error message: '%s'",
                        uid,
                        error,
                    )
        for uid in chunk:
            if uid in messages_raw and is_message_keyword_hit(
                messages_raw[uid], detection_keywords, uid
            ):
                urls = get_unsubscribe_urls(messages_raw[uid], detection_keywords)
                if urls:
                    (message_from, message_date) = get_message_from_and_date(
                        messages_raw[uid]
                    )
                    uids_with_details[uid] = {
                        "uid": uid,
                        "url": urls,
                        "from": message_from,
                        "date": message_date,
                    }

    return uids_with_details


def is_imap_server_supporting_search_capability(
    imap_session: imapclient.IMAPClient,
) -> bool:
    return not (
        len(
            list(
                filter(
                    lambda element: "search" in element.decode("utf-8").lower(),
                    imap_session.capabilities(),
                )
            )
        )
        <= 0
    )


def is_message_keyword_hit(
    raw_message: dict[bytes, bytes], detection_keywords: list[str], uid: int
) -> bool:
    if b"BODY[]" not in raw_message:
        logging.error("Odd Email at UID: %d; SKIPPING....", uid)
        return False

    msg: pyzmail.PyzMessage = pyzmail.PyzMessage.factory(raw_message[b"BODY[]"])
    if msg.html_part:
        message_content = msg.html_part.get_payload().decode("utf-8", errors="replace")
    else:
        message_content = msg.text_part.get_payload().decode("utf-8", errors="replace")

    # check if we can discard the message early because it does not have any keyword hit
    message_content_contains_any_keyword = False
    for keyword in detection_keywords:
        if keyword in message_content or message_content_contains_any_keyword is True:
            message_content_contains_any_keyword = True
    if not message_content_contains_any_keyword:
        return False
    else:
        return True


def get_unsubscribe_urls(
    raw_message: dict[bytes, bytes], detection_keywords: list[str]
) -> set[str]:
    results = set()

    msg: pyzmail.PyzMessage = pyzmail.PyzMessage.factory(raw_message[b"BODY[]"])
    message_content = msg.html_part.get_payload().decode("utf-8", errors="replace")

    parsed_html = bs4.BeautifulSoup(message_content, "html.parser")

    elements = parsed_html.select("a")
    elements.reverse()  # usually this kind of URL are at the bottom of the HTML
    for item in elements:
        current_element = str(item).lower()
        for word in detection_keywords:
            if word.lower() in current_element:
                url = item.get("href")
                if url.strip():
                    results.add(url)

    return results


def get_message_from_and_date(
    raw_message: dict[bytes, bytes]
) -> tuple[tuple, datetime]:
    msg: pyzmail.PyzMessage = pyzmail.PyzMessage.factory(raw_message[b"BODY[]"])
    return (
        tuple(map(lambda element: element.strip(), msg.get_addresses("from")[0])),
        dateutil_parser.parse(msg.get_decoded_header("date")),
    )


def group_by_mail_sender_name_and_sorted_by_date(
    data: dict[int, dict[str, typing.Any]]
) -> dict[str, list[dict[str, typing.Any]]]:
    result: dict[str, list[dict[str, typing.Any]]] = {}

    for key, value in data.items():
        current_key = value["from"][0]
        if current_key not in result.keys():
            result[current_key] = []
        result[current_key].append(value)

    for key in result.keys():
        result[key] = sorted(result[key], key=lambda x: x["date"], reverse=True)

    return result


if __name__ == "__main__":
    main()
