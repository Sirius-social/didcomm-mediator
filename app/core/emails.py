import ssl
import smtplib
from email.mime.text import MIMEText
from typing import Optional

import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content


def check_server(address: str, port: int, username: str, password: str, use_ssl: bool, use_tls: bool) -> (bool, Optional[str]):
    """ Logs in to SMTP server to check credentials and settings
    :return: success, error-msg
    """
    if use_ssl:
        server = smtplib.SMTP_SSL(address, port, timeout=5)
    else:
        server = smtplib.SMTP(address, port, timeout=5)
    server.ehlo()
    if use_tls:
        server.starttls()
        server.ehlo()
    try:
        server.login(username, password)
    except Exception as e:
        return False, "Cannot connect to your SMTP account. Correct your config and try again, details: %s" % str(e)
    else:
        return True, None


def send_email(to: str, from_email: str, subject: str, body: str, credentials: dict) -> (bool, str):
    """
    :return: success, error-msg
    """
    address = credentials.get('address', '')
    port = credentials.get('port', 465)
    username = credentials.get('username', '')
    password = credentials.get('password', '')
    use_ssl = credentials.get('use_ssl') is True
    use_tls = credentials.get('use_tls') is True

    if use_ssl:
        server = smtplib.SMTP_SSL(address, port, timeout=5)
    else:
        server = smtplib.SMTP(address, port, timeout=5)
    server.ehlo()
    if use_tls:
        server.starttls()
        server.ehlo()
    try:
        server.login(username, password)
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to
        server.sendmail(from_email, [to], msg.as_string())
    except Exception as e:
        return False, "Error while send email, details: %s" % str(e)
    else:
        return True, None


def sendgrid_send_email(to: str, subject: str, body: str, credentials: dict) -> (bool, str):
    """
    :return: success, error-msg
    """

    from_email = credentials.get('sendgrid_from_email')
    api_key = credentials.get('sendgrid_api_key')
    try:
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        from_email = Email(from_email)  # Change to your verified sender
        to_email = To(to)  # Change to your recipient
        content = Content("text/plain", body)
        mail = Mail(from_email, to_email, subject, content)
        # Get a JSON-ready representation of the Mail object
        mail_json = mail.get()
        # Send an HTTP POST request to /mail/send
        response = sg.client.mail.send.post(request_body=mail_json)
    except Exception as e:
        return False, "Error while send email, details: %s" % str(e)
    else:
        return True, None
