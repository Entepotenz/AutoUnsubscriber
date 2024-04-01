import logging
import string

import bs4
import click
import dateutil
import pyzmail
from imapclient import imapclient

logging.basicConfig(level=logging.INFO)


@click.command()
@click.option("--email", prompt="Your email address", help="Your email address")
@click.option(
    "--password", prompt="Your password", hide_input=True, help="Your password"
)
@click.option("--imap-server", prompt="IMAP server name", help="IMAP server name")
@click.option(
    "--port", prompt="Port number", default=993, help="Port number for IMAP server"
)
def main(email: str, password: str, imap_server: str, port: int):
    click.echo("Email address: {}".format(email))
    click.echo("Password: {}".format("*" * len(password)))  # Masking password
    click.echo("IMAP server: {}".format(imap_server))
    click.echo("Port: {}".format(port))

    imap_session = login(email, password, imap_server, port)

    detection_keywords = [
        "unsubscribe",
        "subscription",
        "optout",
        "abbestellen",
        "abmelden",
    ]

    data = get_mails_with_detected_keywords(imap_session, detection_keywords)

    data_grouped = group_by_mail_sender_name_and_sorted_by_date(data)

    for key, value in data_grouped.items():
        logging.info(f'{key[0]} - {key[1]} - {value[0]["url"]}')

    imap_session.logout()


def login(
    email: str, password: str, imap_server: str, port: int
) -> imapclient.IMAPClient:
    try:
        imap = imapclient.IMAPClient(imap_server, port=port, ssl=True)
        imap.login(email, password)
        logging.info("Log in successful")
        return imap
    except imapclient.exceptions.IMAPClientError as error:
        logging.error("An error occurred while attempting to log in: {}", error)


def get_mails_with_detected_keywords(
    imap_session: imapclient.IMAPClient, detection_keywords: [string]
):
    imap_session.select_folder("INBOX", readonly=True)

    detection_results = {}
    for keyword in detection_keywords:
        messages = imap_session.search(["TEXT", keyword])
        detection_results[keyword] = messages

    merged_uid_list = set()
    for item in detection_results.values():
        merged_uid_list = set(item).union(merged_uid_list)

    uids_with_details: {string: {}} = {}

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
                                "date": dateutil.parser.parse(
                                    msg.get_decoded_header("date")
                                ),
                            }
                            break
        else:
            logging.error("Odd Email at UID: " + str(uid) + "; SKIPPING....")

    return uids_with_details


def group_by_mail_sender_name_and_sorted_by_date(data):
    result = {}

    for key, value in data.items():
        if value["from"][0] not in result.keys():
            result[value["from"][0]] = []
        result[value["from"][0]].append(value)

    for key in result.keys():
        result[key] = sorted(result[key], key=lambda x: x["date"], reverse=True)

    return result


if __name__ == "__main__":
    main()
