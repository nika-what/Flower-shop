import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)

def _resolve_smtp():
    """
    Resolve SMTP connection settings from env.

    Priority:
    1) Generic SMTP_* vars (SMTP_HOST/SMTP_USER/SMTP_PASSWORD)
    2) Provider-specific vars (gmail/yandex/mailru) based on EMAIL_SMTP_PROVIDER
    """
    if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
        return settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USER, settings.SMTP_PASSWORD, settings.SMTP_FROM

    provider = (settings.EMAIL_SMTP_PROVIDER or '').strip().lower()
    if provider == 'gmail':
        return (
            settings.SMTP_GMAIL_HOST,
            settings.SMTP_GMAIL_PORT,
            settings.SMTP_GMAIL_USER,
            settings.SMTP_GMAIL_PASSWORD,
            settings.SMTP_GMAIL_FROM,
        )
    if provider == 'yandex':
        return (
            settings.SMTP_YANDEX_HOST,
            settings.SMTP_YANDEX_PORT,
            settings.SMTP_YANDEX_USER,
            settings.SMTP_YANDEX_PASSWORD,
            settings.SMTP_YANDEX_FROM,
        )
    if provider in {'mailru', 'mail.ru', 'mail'}:
        return (
            settings.SMTP_MAILRU_HOST,
            settings.SMTP_MAILRU_PORT,
            settings.SMTP_MAILRU_USER,
            settings.SMTP_MAILRU_PASSWORD,
            settings.SMTP_MAILRU_FROM,
        )

    return None


def _build_message(to_email: str, *, from_email: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(body)
    return msg


def send_email_code(to_email: str, *, purpose: str, code: str) -> bool:
    """
    Try to send code via SMTP.
    Returns True if sent, False otherwise.
    """
    subject = {
        'email_verify': 'Подтверждение email',
        'password_reset': 'Код для сброса пароля',
    }.get(purpose, 'Код')

    body = {
        'email_verify': f'Ваш код подтверждения: {code}',
        'password_reset': f'Ваш код для сброса пароля: {code}',
    }.get(purpose, f'Ваш код: {code}')

    smtp = _resolve_smtp()
    if not smtp:
        logger.warning('SMTP is not configured. Not sending email to=%s purpose=%s', to_email, purpose)
        return False

    host, port, user, password, from_email = smtp
    logger.info(
        'SMTP resolved: host=%s port=%s user_set=%s password_set=%s from=%s to=%s purpose=%s',
        host,
        port,
        bool(user),
        bool(password),
        from_email,
        to_email,
        purpose,
    )

    if not host or not port or not user or not password:
        logger.warning(
            'SMTP credentials are missing. Not sending email to=%s purpose=%s',
            to_email,
            purpose,
        )
        return False

    message = _build_message(to_email, from_email=from_email, subject=subject, body=body)
    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(message)
        return True
    except Exception:
        logger.exception('Failed to send email code.')
        return False

