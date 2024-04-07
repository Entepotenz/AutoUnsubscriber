import logging
from datetime import datetime

import bs4
import click
import pyzmail
from dateutil import parser as dateutil_parser
from imapclient import imapclient

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
def main(email: str, password: str, imap_server: str, port: int, tls: bool) -> None:
    click.echo("Email address: {}".format(email))
    click.echo("Password: {}".format("*" * len(password)))  # Masking password
    click.echo("IMAP server: {}".format(imap_server))
    click.echo("Port: {}".format(port))
    click.echo("TLS: {}".format(tls))

    detection_keywords = [
        "unsubscribe",
        "subscription",
        "optout",
        "abbestellen",
        "abmelden",
    ]

    with login(email, password, imap_server, port, tls) as imap_session:
        data = get_mails_with_detected_keywords(imap_session, detection_keywords)

        data_grouped = group_by_mail_sender_name_and_sorted_by_date(data)

        for key, value in data_grouped.items():
            logging.info(f'{key} - {value[0]["from"][0][1]} - {value[0]["url"]}')


def login(
    email: str, password: str, imap_server: str, port: int, tls: bool
) -> imapclient.IMAPClient:
    try:
        imap = imapclient.IMAPClient(imap_server, port=port, ssl=tls, timeout=30)
        imap.login(email, password)
        logging.info("Log in successful")
        return imap
    except imapclient.exceptions.IMAPClientError as error:
        logging.error("An error occurred while attempting to log in: {}", error)
    except Exception as error:
        logging.error("An error occurred while attempting to log in: {}", error)


def get_mails_with_detected_keywords(
    imap_session: imapclient.IMAPClient, detection_keywords: list[str]
) -> dict[int, dict[str, any]]:
    if not imap_session.folder_exists("INBOX"):
        logging.warning("'INBOX' folder does not exist!")
    logging.debug("%s", imap_session.list_folders())
    imap_session.select_folder("INBOX", readonly=True)

    is_imap_search_supported = is_imap_server_supporting_search_capability(imap_session)

    detection_results = {}
    merged_uid_list: set[int] = set()

    if is_imap_search_supported:
        for keyword in detection_keywords:
            messages = imap_session.search(["TEXT", keyword])
            detection_results[keyword] = messages

        for item in detection_results.values():
            merged_uid_list = set(item).union(merged_uid_list)
    else:
        logging.warning(
            "IMAP server does not support 'search' -> falling back to downloading messages (this can take some time)"
        )
        all_uids_in_inbox = imap_session.search()
        merged_uid_list = set(all_uids_in_inbox)

    uids_with_details: dict[int, dict[str, any]] = {}

    messages_raw = imap_session.fetch(merged_uid_list, ["BODY[]"])
    for uid in merged_uid_list:
        if is_message_keyword_hit(messages_raw[uid], detection_keywords, uid):
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
    message_content = msg.html_part.get_payload().decode("utf-8", errors="replace")

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


def get_message_from_and_date(raw_message: dict[bytes, bytes]) -> tuple[str, datetime]:
    msg: pyzmail.PyzMessage = pyzmail.PyzMessage.factory(raw_message[b"BODY[]"])
    return (
        msg.get_addresses("from"),
        dateutil_parser.parse(msg.get_decoded_header("date")),
    )


def group_by_mail_sender_name_and_sorted_by_date(
    data: dict[int, dict[str, any]]
) -> dict[str, list[dict[str, any]]]:
    result: dict[str, list[dict[str, any]]] = {}

    for key, value in data.items():
        current_key = value["from"][0][0]
        if current_key not in result.keys():
            result[current_key] = []
        result[current_key].append(value)

    for key in result.keys():
        result[key] = sorted(result[key], key=lambda x: x["date"], reverse=True)

    return result


if __name__ == "__main__":
    main()
