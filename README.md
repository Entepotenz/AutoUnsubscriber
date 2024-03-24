### AutoUnsubscriber

Warning: the code is pretty rough and beta.
I removed the option to automatically delete mails so you can use this program without exposing your mail inbox to any danger.

This is a fork of: https://github.com/0cwa/AutoUnsubscriber/tree/master which has been forked from https://github.com/adsnash/AutoUnsubscriber

This program is an email auto-unsubscriber. Depending on your email provider and settings, it may require you to allow access to less secure apps.

It uses IMAP to log into your email. From there, it goes through every email with "unsubscribe" in the body, parses the HTML, and uses regex to search through anchor tags for keywords that indicate an unsubscribe link (unsubscribe, optout, etc). If it finds a match, it grabs the href link and puts the address and link in a list.

After the program has a list of emails and links, for each address in the list, it gives the user the option to navigate to the unsubscribe link and to delete emails with unsubscribe in the body from the sender.

Once the program finishes going through the list, it gives the user the option to run the program again on the same email address, run it on a different email address, or quit the program.

------
### Usage with docker

```shell
docker build --pull --tag AutoUnsubscriber -f Dockerfile .
docker run -it --rm AutoUnsubscriber:latest
```


