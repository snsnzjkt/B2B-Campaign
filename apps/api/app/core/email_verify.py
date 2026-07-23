import dns.exception
import dns.resolver
from email_validator import EmailNotValidError, validate_email


def verify_email(email: str) -> bool:
    try:
        valid = validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        return False

    try:
        dns.resolver.resolve(valid.domain, "MX")
    except dns.exception.DNSException:
        return False
    return True
