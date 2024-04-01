#!/usr/bin/env python3

import pyzmail
import imapclient
import bs4
import getpass
import re
import sys
import ssl
import logging

# List of accepted service providers and respective imap link
servers = [
    ("Gmail", "imap.gmail.com"),
    ("Outlook", "imap-mail.outlook.com"),
    ("Hotmail", "imap-mail.outlook.com"),
    ("Yahoo", "imap.mail.yahoo.com"),
    ("ATT", "imap.mail.att.net"),
    ("Comcast", "imap.comcast.net"),
    ("Verizon", "incoming.verizon.net"),
    ("AOL", "imap.aol.com"),
    ("Zoho", "imap.zoho.com"),
    ("GMX", "imap.gmx.com"),
]
# Rewrote with dictionaries
serverD = {
    "Gmail": {"imap": "imap.gmail.com", "domains": ["@gmail.com"]},
    "Outlook/Hotmail": {
        "imap": "imap-mail.outlook.com",
        "domains": ["@outlook.com", "@hotmail.com"],
    },
    "Yahoo": {"imap": "imap.mail.yahoo.com", "domains": ["@yahoo.com"]},
    "ATT": {"imap": "imap.mail.att.net", "domains": ["@att.net"]},
    "Comcast": {"imap": "imap.comcast.net", "domains": ["@comcast.net"]},
    "Verizon": {"imap": "incoming.verizon.net", "domains": ["@verizon.net"]},
    "AOL": {"imap": "imap.aol.com", "domains": ["@aol.com"]},
    "Zoho": {"imap": "imap.zoho.com", "domains": ["@zoho.com"]},
    "GMX": {"imap": "imap.gmx.com", "domains": ["@gmx.com"]},
}

# Keywords for unsubscribe link - add more if found
WORDS = ["unsubscribe", "subscription", "optout", "abbestellen", "abmelden"]


class AutoUnsubscriber:
    def __init__(self):
        self.context = None
        self.words = WORDS
        self.email = ""
        self.user = None
        self.password = ""
        self.imap = None
        self.goToLinks = False
        self.delEmails = False
        self.senderList = []
        self.noLinkList = []
        self.providers = []
        # server name is later matched against second level domain names
        for server in servers:
            self.providers.append(re.compile(server[0], re.I))
        # TODO maybe add support for servers with a
        # company name different than their domain name...

    # Get initial user info - email, password, and service provider
    def get_info(self):
        logging.info(
            "This program searches your email for junk mail to unsubscribe from and list the links to unsubscribe"
        )
        logging.info("Supported emails: Gmail, Outlook, Hotmail, Yahoo, AOL, Zoho,")
        logging.info("GMX, AT&T, Comcast, and Verizon")
        logging.info("Please note: you may need to allow access to less secure apps")
        get_email = True
        while get_email:
            self.email = str.lower(input("\nEnter your email address: "))
            for prov in serverD:
                match = False
                for domain in serverD[prov]["domains"]:
                    if domain in self.email:
                        logging.info("Looks like you're using a " + prov + " account")
                        self.user = (prov, serverD[prov]["imap"])
                        get_email = False
                        match = True
                        break
                if match:
                    break
            if self.user is None:
                logging.warning(
                    "Email type not recognized, enter an imap server, or press enter to try a different email address:"
                )
                myimap = input("\n[myimapserver.tld] | [enter] : ")
                if myimap:
                    self.user = ("Self-defined IMAP", myimap)
                    logging.info("You are using a " + self.user[0] + " account!")
                    get_email = False
                    break
                logging.error("Try a different account")
        self.password = getpass.getpass("Enter password for " + self.email + ": ")

    # Log in to IMAP server, argument determines whether readonly or not
    def login(self, read=True):
        try:
            self.imap = imapclient.IMAPClient(self.user[1], ssl=True)
            self.imap._MAXLINE = 10000000
            self.imap.login(self.email, self.password)
            self.imap.select_folder("INBOX", readonly=read)
            logging.info("Log in successful")
            return True
        except:
            logging.error(
                "An error occurred while attempting to log in, please try again"
            )
            return False

    # Attempt to log in to server. On failure, force user to re-enter info
    def access_server(self, readonly=True):
        if self.email == "":
            self.get_info()
        attempt = self.login(readonly)
        if not attempt:
            self.new_email()
            self.access_server(readonly)

    # Search for emails with unsubscribe in the body. If sender not already in
    # senderList, parse email for unsubscribe link. If link found, add name, email,
    # link (plus metadata for decisions) to senderList. If not, add to noLinkList.
    def get_emails(self):
        logging.info("Getting emails with unsubscribe in the body")
        uid_list = self.imap.search(["TEXT", "unsubscribe"])
        raw = self.imap.fetch(uid_list, ["BODY[]"])
        logging.info("Getting links and addresses")
        for uid in uid_list:
            # If Body exists (resolves weird error with empty body emails from Yahoo),
            # then Get address and check if sender already in senderList
            if b"BODY[]" in raw[uid]:
                msg = pyzmail.PyzMessage.factory(raw[uid][b"BODY[]"])
            else:
                logging.info("Odd Email at UID: " + str(uid) + "; SKIPPING....")
                continue
            sender = msg.get_addresses("from")
            try_sender = True
            for spammers in self.senderList:
                if sender[0][1] in spammers:
                    try_sender = False
            # If not, search for link
            if try_sender:
                # Encode and decode to cp437 to handle unicode errors and get
                # rid of characters that can't be printed by Windows command line
                # which has default setting of cp437
                sender_name = sender[0][0].encode("cp437", "ignore")
                sender_name = sender_name.decode("cp437")
                logging.info("Searching for unsubscribe link from " + str(sender_name))
                url = False
                # Parse html for elements with anchor tags
                if html_piece := msg.html_part:
                    html = html_piece.get_payload().decode("utf-8", errors="replace")
                    soup = bs4.BeautifulSoup(html, "html.parser")
                    elements = soup.select("a")
                    # For each anchor tag, use regex to search for keywords
                    elements.reverse()
                    # search starting at the bottom of email
                    for elem in elements:
                        current_element = str(elem).lower()
                        for word in self.words:
                            # If one is found, get the url
                            if word.lower() in current_element:
                                logging.info("Link found")
                                url = elem.get("href")
                                break
                        if url:
                            break
                # If link found, add info to senderList
                # format: (Name, email, link, go to link)
                # If no link found, add to noLinkList
                if url:
                    self.senderList.append(
                        [sender_name, sender[0][1], url, False, False]
                    )
                else:
                    logging.info("No link found")
                    not_in_list = True
                    for noLinkers in self.noLinkList:
                        if sender[0][1] in noLinkers:
                            not_in_list = False
                    if not_in_list:
                        self.noLinkList.append([sender[0][0], sender[0][1]])
        logging.info("Logging out of email server")
        self.imap.logout()

    # Display info about which providers links were/were not found for
    def display_email_info(self):
        if self.noLinkList:
            logging.warning("Could not find unsubscribe links from these senders:")
            no_list = "| "
            for i in range(len(self.noLinkList)):
                no_list += str(self.noLinkList[i][0]) + " | "
            logging.info(no_list)
        if self.senderList:
            logging.info("Found unsubscribe links from these senders:")
            full_list = "| "
            for i in range(len(self.senderList)):
                full_list += str(self.senderList[i][0]) + " | "
            logging.info(full_list)

    # Allow user to decide which unsubscribe links to follow/emails
    def decisions(self):
        self.display_email_info()
        logging.info("You may now decide which emails to unsubscribe from")
        logging.info(
            "Navigating to unsubscribe links may not automatically unsubscribe you"
        )
        for j in range(len(self.senderList)):
            self.senderList[j][3] = True
            self.goToLinks = True

    # Navigate to selected unsubscribe, 10 at a time
    def open_links(self):
        if not self.goToLinks:
            logging.info("No unsubscribe links selected to navigate to")
        else:
            logging.info("Unsubscribe links:")
            counter = 0
            for i in range(len(self.senderList)):
                if self.senderList[i][3]:
                    logging.info(self.senderList[i][2])
                    counter += 1
                    if counter == 10:
                        logging.info("Navigating to unsubscribe links")
                        cont = input("Press 'Enter' to continue: ")
                        counter = 0

    # For re-running on same email. Clear lists, reset flags, but use same info
    # for email, password, email provider, etc.
    def run_again(self):
        self.goToLinks = False
        self.delEmails = False
        self.senderList = []
        self.noLinkList = []

    # Reset everything to get completely new user info
    def new_email(self):
        self.email = ""
        self.user = None
        self.password = ""
        self.imap = None
        self.run_again()

    # Called after program has run, allow user to run again on same email, run
    # on a different email, or quit the program
    def next_move(self):
        logging.info(
            "Run this program again on the same email, a different email, or quit?"
        )
        while True:
            logging.info("Press 'A' to run again on " + str(self.email))
            logging.info("Press 'D' to run on a different email address")
            again = input("Press 'Q' to quit: ")
            if again.lower() == "a":
                logging.info("Running program again for " + str(self.email))
                self.run_again()
                return True
            elif again.lower() == "d":
                logging.info("Preparing program to run on a different email address")
                self.new_email()
                return False
            elif again.lower() == "q":
                logging.info("So long, space cowboy!")
                sys.exit()
            else:
                logging.info("Invalid choice, please enter 'A', 'D' or 'Q'.")

    # Full set of program commands. Works whether it has user info or not
    def full_process(self):
        self.access_server()
        self.get_emails()
        if self.senderList:
            self.decisions()
            self.open_links()
        else:
            logging.info("No unsubscribe links detected")

    # Loop to run program and not quit until told to by user or closed
    def usage_loop(self):
        self.full_process()
        while True:
            self.next_move()
            self.full_process()


def main():
    auto = AutoUnsubscriber()
    auto.usage_loop()


if __name__ == "__main__":
    main()
