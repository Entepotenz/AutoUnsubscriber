import click


@click.command()
@click.option('--email', prompt='Your email address', help='Your email address')
@click.option('--password', prompt='Your password', hide_input=True, help='Your password')
@click.option('--imap-server', prompt='IMAP server name', help='IMAP server name')
@click.option('--port', prompt='Port number', default=993, help='Port number for IMAP server')
def main(email: str, password, imap_server, port):
    click.echo('Email address: {}'.format(email))
    click.echo('Password: {}'.format('*' * len(password)))  # Masking password
    click.echo('IMAP server: {}'.format(imap_server))
    click.echo('Port: {}'.format(port))


def login(self, read=True):
    try:
        self.imap = imapclient.IMAPClient(self.user[1], ssl=True)
        self.imap._MAXLINE = 10000000
        self.imap.login(self.email, self.password)
        self.imap.select_folder("INBOX", readonly=read)
        logging.info("Log in successful")
        return True
    except:
        logging.error("An error occurred while attempting to log in, please try again")
        return False

if __name__ == '__main__':
    main()
