import re

_ip_regex = re.compile('((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\\.|$)){4}')


def validate_ip(address: str) -> bool:
    return _ip_regex.match(address) is not None
