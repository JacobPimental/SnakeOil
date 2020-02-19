# SnakeOil
Spam Trap created in Python

Will convert your server into a fake Open SMTP Relay

Sends logged data to Slack for analysis

## Usage:
`python snakeoil.py <slack_token>

Default port is 2525, to create a mail server I would recommend using iptables to route traffic from port 25 to 2525 like so:
`iptables -t nat -A PREROUTING -p tcp --dport 25 -j REDIRECT --to-port 2525`

Now all you need to do is wait for spam bots to send you mail
