from smtpd import *
import asyncore
import email
import hashlib
import slack
import os
import sys
import re
from bs4 import BeautifulSoup

class SnakeOil(SMTPServer):

    def __init__(self, localaddr, remoteaddr, token):
        """Initializes the smtpd server

        Args:
            localaddr: address to host the server on
            remoteaddr: remote address to forward email to
            token: slack token used to connect to slack channel
        """
        super().__init__(localaddr, remoteaddr)
        self.client = slack.WebClient(token=token)


    def get_parts(self, e):
        """Gets different parts of the email we want to parse out.

        Args:
            e: Email object created by smtpd library

        Returns:
            dict: object containing different parts of the email including
            body_text, body_html, and attachments
        """
        parts = {'body_html':None,
                 'body_text':None}
        attachments = {}
        for p in e.walk():
            parts['Reply-To'] = p.get('Reply-To', '')
            f = p.get_filename()
            content_type = p.get_content_type()
            if f:
                attachments[f] = p.get_payload(decode=True)
                continue
            if content_type == 'text/html':
                parts['body_html'] = p.get_payload(decode=True)
            if content_type == 'text/text':
                parts['body_text'] = p.get_payload(decode=True)
        parts['attachments'] = attachments
        return parts


    def write_attachments(self, attachments):
        """Writes attachments to disk.

        Args:
            attachments: dict where key is the attachment name and value is the
            data in the file attachment
        """
        for a in attachments.keys():
            dat = attachments[a]
            with open(a, 'wb') as f:
                f.write(dat)
                f.close()


    def upload_attachments(self, attachments):
        """Uploads attachments to Slack.

        Args:
            attachments: dict where key is the attachment name and value is the
            data in the file attachment
        """
        for a in attachments.keys():
            dat = attachments[a]
            md5 = hashlib.md5(dat).hexdigest()
            self.client.files_upload(channels='#general',
                                     initial_comment=md5,
                                     filename=a,
                                     file=a)
            os.remove(a)


    def get_links_html(self, body):
        """Gets links within html content.

        Args:
            body: html body of an email

        Returns:
            list: List of links in the html blob
        """
        links = []
        soup = BeautifulSoup(body)
        a_tag = soup.findAll('a', attrs={'href': re.compile('^http.*://')})
        for tag in a_tag:
            links.append(tag.get('href'))
        return links


    def get_links_text(self, body):
        """Gets links within a blob of plaintext.

        Args:
            body: text blob of the body of an email

        Returns:
            list: List of links in the text blob
        """
        links = re.findall(r'https?://[A-Za-z0-9\.\/]+',
                           body)
        return links


    def upload_links(self, links):
        """Uploads links to Slack.

        Args:
            links: List of links that were parsed out
        """
        for link in links:
            self.client.chat_postMessage(channel='#general',
                                         text=link)


    def upload_email(self, data, subject):
        """Uploads email object to Slack.

        Args:
            data: email data from smtpd library
            subject: email subject, also used as file name
        """
        with open('{}.msg'.format(subject), 'wb') as f:
            f.write(data)
            f.close()
        self.client.files_upload(channels='#general',
                                 filename='{}.msg'.format(subject),
                                 file='{}.msg'.format(subject))
        os.remove('{}.msg'.format(subject))


    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        """Inherited class from smtpd library that processes incoming email.

        Args:
            peer: tuple containing the incoming IP and the port it is coming
            from
            mailfrom: email address that the email is coming from
            rcpttos: recipients to receive the email
            data: overall email data

        Returns:
            None: Must return something to send an OK to the original client
        """
        try:
            e = email.message_from_bytes(data)
            headers = {'IP':peer,
                       'From':mailfrom,
                       'Recipients':','.join(rcpttos),
                       'Subject':e['Subject']
                      }
            parts = self.get_parts(e)
            links = []
            if parts['body_html']:
                links = self.get_links_html(parts['body_html'])
            elif parts['body_text']:
                links = self.get_links_text(parts['body_text'])

            msg_text = ('IP : {}\nFrom : {}\n'.format(headers['IP'],
                                                      headers['From']) +
                        'Rcpts : {}\nSubject : {}'.format(headers['Recipients'],
                                                          headers['Subject']) +
                        'Reply-To: {}'.format(parts['Reply-To']) +
                        'Num Links : {}\nNum Att : {}'.format(len(links),
                                                              len(parts['attachments'])))
            self.client.chat_postMessage(channel='#general',
                                         text=msg_text)

            if len(links) > 0:
                self.upload_links(links)
            if len(parts['attachments']) > 0:
                self.write_attachments(parts['attachments'])
                self.upload_attachments(parts['attachments'])
            self.upload_email(data, e['Subject'])
        except Exception as e:
            print(e)
        return None


if __name__ == '__main__':
    args = sys.argv
    if len(args) < 2:
        print('Usage: python snakeoil.py <slack_token>')
        sys.exit()
    h = SnakeOil(('0.0.0.0', 2525), None, args[1])
    try:
        asyncore.loop()
    except Exception as e:
        print(e)
