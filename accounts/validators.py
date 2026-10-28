import re
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError

# Recognized valid top-level domain extensions
VALID_DOMAIN_EXTENSIONS = {
    'com', 'in', 'org', 'net', 'edu', 'gov', 'mil',
    'io', 'ai', 'app', 'dev', 'me', 'info', 'biz',
    'xyz', 'site', 'online', 'tech', 'store', 'club',
    'us', 'uk', 'ca', 'au', 'de', 'fr', 'jp',
}

# Recognized compound second-level domain extensions
VALID_COMPOUND_EXTENSIONS = {
    'co.in', 'org.in', 'net.in', 'ac.in', 'gov.in', 'edu.in', 'res.in',
    'co.uk', 'org.uk', 'ac.uk', 'gov.uk', 'com.au', 'net.au', 'org.au'
}

# Well-known provider extensions (catches typos like @gmail.co instead of @gmail.com)
PROVIDER_ALLOWED_EXTENSIONS = {
    'gmail': {'com'},
    'yahoo': {'com', 'in', 'co.in', 'co.uk'},
    'hotmail': {'com'},
    'outlook': {'com', 'in'},
    'icloud': {'com'},
}


def validate_email_address(email):
    """
    Validates that the email address:
    1. Is non-empty and passes Django's EmailValidator.
    2. Contains a valid domain structure with a recognized domain extension (such as .com, .in, or .org).
    3. Rejects incomplete or invalid domain extensions (e.g. 'rajakshail2@gmail.co', 'user@domain.c', 'user@gmail').

    Returns a tuple: (is_valid: bool, error_message: str)
    """
    if not email or not isinstance(email, str):
        return False, "Enter a valid email address."

    email = email.strip()
    if not email:
        return False, "Enter a valid email address."

    # 1. Standard Django EmailValidator format check
    django_validator = EmailValidator(message="Enter a valid email address.")
    try:
        django_validator(email)
    except ValidationError:
        return False, "Enter a valid email address."

    if '@' not in email:
        return False, "Enter a valid email address."

    local_part, domain = email.rsplit('@', 1)
    domain = domain.lower().strip()

    # Domain must contain at least one dot
    if '.' not in domain:
        return False, "Enter a valid email address. Please provide a valid domain extension (such as .com, .in, or .org)."

    parts = domain.split('.')
    # Check for empty parts (e.g., user@.com or user@domain..com)
    if any(not p for p in parts):
        return False, "Enter a valid email address."

    # Domain label character checks
    for part in parts:
        if not re.match(r'^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$', part):
            return False, "Enter a valid email address."

    # Check for compound extension (e.g. .co.in, .gov.in)
    has_valid_ext = False
    if len(parts) >= 3:
        compound = f"{parts[-2]}.{parts[-1]}"
        if compound in VALID_COMPOUND_EXTENSIONS:
            has_valid_ext = True

    # Check for standard TLD extension (e.g. .com, .in, .org)
    tld = parts[-1]
    if not has_valid_ext:
        if tld in VALID_DOMAIN_EXTENSIONS:
            has_valid_ext = True

    if not has_valid_ext:
        return False, "Enter a valid email address. Please provide a valid domain extension (such as .com, .in, or .org)."

    # 3. Provider-specific typo protection (e.g., gmail.co -> incomplete/invalid)
    if len(parts) >= 2:
        provider = parts[-2]
        if provider in PROVIDER_ALLOWED_EXTENSIONS:
            allowed = PROVIDER_ALLOWED_EXTENSIONS[provider]
            ext = f"{parts[-2]}.{parts[-1]}" if len(parts) >= 3 and f"{parts[-2]}.{parts[-1]}" in VALID_COMPOUND_EXTENSIONS else tld
            if tld not in allowed and ext not in allowed:
                return False, f"Enter a valid email address. Please provide a valid domain extension for @{provider} (e.g. @{provider}.com)."

    return True, ""


def validate_custom_email(value):
    """
    Django field/form validator callable.
    Raises ValidationError if the email address is invalid or has an incomplete domain.
    """
    is_valid, error_msg = validate_email_address(value)
    if not is_valid:
        raise ValidationError(error_msg)
