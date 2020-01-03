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
        super().__init__(localaddr, remoteaddr)
        self.client = slack.WebClient(token=token)

    def get_parts(self, e):
        parts = {'body':None}
        attachments = {}
        for p in e.walk():
            f = p.get_filename()
            content_type = p.get_content_type()
            if f and 'image' not in content_type:
                attachments[f] = p.get_payload(decode=True)
                continue
            if content_type == 'text/html':
                parts['body'] = p.get_payload(decode=True)
        parts['attachments'] = attachments
        return parts

    def write_attachments(self, attachments):
        for a in attachments.keys():
            dat = attachments[a]
            with open(a, 'wb') as f:
                f.write(dat)
                f.close()

    def upload_attachments(self, attachments):
        for a in attachments.keys():
            dat = attachments[a]
            md5 = hashlib.md5(dat).hexdigest()
            self.client.files_upload(channels='#general',
                                     initial_comment=md5,
                                     filename=a,
                                     file=a)
            os.remove(a)

    def get_links(self, body):
        links = []
        soup = BeautifulSoup(body)
        a_tag = soup.findAll('a', attrs={'href': re.compile('^http.*://')})
        for tag in a_tag:
            links.append(tag.get('href'))
        return links

    def upload_links(self, links):
        for link in links:
            self.client.chat_postMessage(channel='#general',
                                         text=link)

    def upload_email(self, data, subject):
        with open('{}.msg'.format(subject), 'wb') as f:
            f.write(data)
            f.close()
        self.client.files_upload(channels='#general',
                                 filename='{}.msg'.format(subject),
                                 file='{}.msg'.format(subject))
        os.remove('{}.msg'.format(subject))

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        try:
            e = email.message_from_bytes(data)
            headers = {'IP':peer,
                       'From':mailfrom,
                       'Recipients':','.join(rcpttos),
                       'Subject':e['Subject']
                      }
            parts = self.get_parts(e)
            links = []
            if parts['body']:
                links = self.get_links(parts['body'])

            msg_text = ('IP : {}\nFrom : {}\n'.format(headers['IP'],
                                                      headers['From']) +
                        'Rcpts : {}\nSubject : {}'.format(headers['Recipients'],
                                                          headers['Subject']) +
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
