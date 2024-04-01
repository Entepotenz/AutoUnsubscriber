#!/usr/bin/env python3

import pyzmail
import imapclient
import bs4
import getpass
import re
import sys
import ssl

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
    ("ProtonMail", "127.0.0.1"),
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
    "ProtonMail": {"imap": "127.0.0.1", "domains": ["@protonmail.com", "@pm.me"]},
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
        print(
            "This program searches your email for junk mail to unsubscribe from and list the links to unsubscribe"
        )
        print("Supported emails: Gmail, Outlook, Hotmail, Yahoo, AOL, Zoho,")
        print("GMX, AT&T, Comcast, ProtonMail (Bridge), and Verizon")
        print("Please note: you may need to allow access to less secure apps")
        get_email = True
        while get_email:
            self.email = str.lower(input("\nEnter your email address: "))
            for prov in serverD:
                match = False
                for domain in serverD[prov]["domains"]:
                    if domain in self.email:
                        print("\nLooks like you're using a " + prov + " account\n")
                        self.user = (prov, serverD[prov]["imap"])
                        get_email = False
                        match = True
                        break
                if match:
                    break
            if self.user is None:
                print(
                    "\nEmail type not recognized, enter an imap server, or press enter to try a different email address:\n"
                )
                myimap = input("\n[myimapserver.tld] | [enter] : ")
                if myimap:
                    self.user = ("Self-defined IMAP", myimap)
                    print("\nYou are using a " + self.user[0] + " account!\n")
                    get_email = False
                    break
                print("\nTry a different account")
        self.password = getpass.getpass("Enter password for " + self.email + ": ")

    # Log in to IMAP server, argument determines whether readonly or not
    def login(self, read=True):
        try:
            # ProtonMail Bridge Support - Requires unverified STARTTLS and changing ports
            if self.user[0] == "ProtonMail":
                print(
                    "\nProtonMail require ProtonMail Bridge installed, make sure you've used the password Bridge gives you."
                )
                self.context = ssl.create_default_context()
                self.context.check_hostname = False
                self.context.verify_mode = ssl.CERT_NONE
                self.imap = imapclient.IMAPClient(self.user[1], port=1143, ssl=False)
                self.imap.starttls(ssl_context=self.context)
            else:
                self.imap = imapclient.IMAPClient(self.user[1], ssl=True)
            self.imap._MAXLINE = 10000000
            self.imap.login(self.email, self.password)
            self.imap.select_folder("INBOX", readonly=read)
            print("\nLog in successful\n")
            return True
        except:
            print("\nAn error occurred while attempting to log in, please try again\n")
            return False

    # Attempt to log in to server. On failure, force user to re-enter info
    def access_server(self, readonly=True):
        if self.email == "":
            self.get_info()
        attempt = self.login(readonly)
        if not attempt:
            self.newEmail()
            self.access_server(readonly)

    # Search for emails with unsubscribe in the body. If sender not already in
    # senderList, parse email for unsubscribe link. If link found, add name, email,
    # link (plus metadata for decisions) to senderList. If not, add to noLinkList.
    def get_emails(self):
        print("Getting emails with unsubscribe in the body\n")
        uid_list = self.imap.search(["TEXT", "unsubscribe"])
        raw = self.imap.fetch(uid_list, ["BODY[]"])
        print("Getting links and addresses\n")
        for uid in uid_list:
            # If Body exists (resolves weird error with empty body emails from Yahoo),
            # then Get address and check if sender already in senderList
            if b"BODY[]" in raw[uid]:
                msg = pyzmail.PyzMessage.factory(raw[uid][b"BODY[]"])
            else:
                print("Odd Email at UID: " + str(uid) + "; SKIPPING....")
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
                print("Searching for unsubscribe link from " + str(sender_name))
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
                                print("Link found")
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
                    print("No link found")
                    notInList = True
                    for noLinkers in self.noLinkList:
                        if sender[0][1] in noLinkers:
                            notInList = False
                    if notInList:
                        self.noLinkList.append([sender[0][0], sender[0][1]])
        print("\nLogging out of email server\n")
        self.imap.logout()

    # Display info about which providers links were/were not found for
    def displayEmailInfo(self):
        if self.noLinkList:
            print("Could not find unsubscribe links from these senders:")
            noList = "| "
            for i in range(len(self.noLinkList)):
                noList += str(self.noLinkList[i][0]) + " | "
            print(noList)
        if self.senderList:
            print("\nFound unsubscribe links from these senders:")
            fullList = "| "
            for i in range(len(self.senderList)):
                fullList += str(self.senderList[i][0]) + " | "
            print(fullList)

    # Allow user to decide which unsubscribe links to follow/emails
    def decisions(self):
        def choice(userInput):
            if userInput.lower() == "y":
                return True
            elif userInput.lower() == "n":
                return False
            else:
                return None

        self.displayEmailInfo()
        print("\nYou may now decide which emails to unsubscribe from")
        print("Navigating to unsubscribe links may not automatically unsubscribe you")
        for j in range(len(self.senderList)):
            self.senderList[j][3] = True
            self.goToLinks = True

    # Navigate to selected unsubscribe, 10 at a time
    def openLinks(self):
        if not self.goToLinks:
            print("\nNo unsubscribe links selected to navigate to")
        else:
            print("\nUnsubscribe links:")
            counter = 0
            for i in range(len(self.senderList)):
                if self.senderList[i][3]:
                    print(self.senderList[i][2])
                    counter += 1
                    if counter == 10:
                        print("Navigating to unsubscribe links")
                        cont = input("Press 'Enter' to continue: ")
                        counter = 0

    # For re-running on same email. Clear lists, reset flags, but use same info
    # for email, password, email provider, etc.
    def runAgain(self):
        self.goToLinks = False
        self.delEmails = False
        self.senderList = []
        self.noLinkList = []

    # Reset everything to get completely new user info
    def newEmail(self):
        self.email = ""
        self.user = None
        self.password = ""
        self.imap = None
        self.runAgain()

    # Called after program has run, allow user to run again on same email, run
    # on a different email, or quit the program
    def nextMove(self):
        print(
            "\nRun this program again on the same email, a different email, or quit?\n"
        )
        while True:
            print("Press 'A' to run again on " + str(self.email))
            print("Press 'D' to run on a different email address")
            again = input("Press 'Q' to quit: ")
            if again.lower() == "a":
                print("\nRunning program again for " + str(self.email) + "\n")
                self.runAgain()
                return True
            elif again.lower() == "d":
                print("\nPreparing program to run on a different email address\n")
                self.newEmail()
                return False
            elif again.lower() == "q":
                print("\nSo long, space cowboy!\n")
                sys.exit()
            else:
                print("\nInvalid choice, please enter 'A', 'D' or 'Q'.\n")

    # Full set of program commands. Works whether it has user info or not
    def fullProcess(self):
        self.access_server()
        self.get_emails()
        if self.senderList:
            self.decisions()
            self.openLinks()
        else:
            print("No unsubscribe links detected")

    # Loop to run program and not quit until told to by user or closed
    def usageLoop(self):
        self.fullProcess()
        while True:
            self.nextMove()
            self.fullProcess()


def main():
    Auto = AutoUnsubscriber()
    Auto.usageLoop()


if __name__ == "__main__":
    main()
