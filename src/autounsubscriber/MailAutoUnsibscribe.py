import logging
from typing import Any, Dict, List

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
) -> dict[int, dict[str, Any]]:
    imap_session.select_folder("INBOX", readonly=True)

    detection_results = {}
    for keyword in detection_keywords:
        messages = imap_session.search(["TEXT", keyword])
        detection_results[keyword] = messages

    merged_uid_list: set[int] = set()
    for item in detection_results.values():
        merged_uid_list = set(item).union(merged_uid_list)

    uids_with_details: dict[int, dict[str, Any]] = {}

    messages_raw = imap_session.fetch(merged_uid_list, ["BODY[]"])
    for uid in merged_uid_list:
        if b"BODY[]" in messages_raw[uid]:
            msg: pyzmail.PyzMessage = pyzmail.PyzMessage.factory(
                messages_raw[uid][b"BODY[]"]
            )
            html = msg.html_part.get_payload().decode("utf-8", errors="replace")
            parsed_html = bs4.BeautifulSoup(html, "html.parser")

            elements = parsed_html.select("a")
            elements.reverse()
            for item in elements:
                if uid in uids_with_details.keys():
                    break

                current_element = str(item).lower()
                for word in detection_keywords:
                    if word.lower() in current_element:
                        url = item.get("href")
                        if url.strip():
                            uids_with_details[uid] = {
                                "uid": uid,
                                "url": url,
                                "from": msg.get_addresses("from"),
                                "date": dateutil_parser.parse(
                                    msg.get_decoded_header("date")
                                ),
                            }
                            break
        else:
            logging.error("Odd Email at UID: " + str(uid) + "; SKIPPING....")

    return uids_with_details


def group_by_mail_sender_name_and_sorted_by_date(
    data: Dict[int, Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}

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
