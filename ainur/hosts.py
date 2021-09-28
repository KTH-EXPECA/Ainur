import re

from marshmallow import Schema, fields

_ip_regex = re.compile('((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\\.|$)){4}')


class IPv4Address(Schema):
    address = fields.Str(validate=lambda v: _ip_regex.match(v) is None)
    prefix = fields.Int(validate=lambda v: 0 < v <= 32)


class NetworkInterface(Schema):
    name = fields.Str()
    ip = fields.Nested(IPv4Address)


class Host(Schema):
    name = fields.Str()
    mgmt_nic = fields.Nested(NetworkInterface)


class WorkloadHost(Host):
    wkld_nic = fields.Nested(NetworkInterface)
