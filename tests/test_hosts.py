from typing import Collection
from unittest import TestCase

from ainur.hosts import *
from ainur.hosts import _BaseNetplanIfaceCfg


class TestNetplanConfigs(TestCase):
    # language=YAML
    valid_eth_cfg = '''
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      addresses:
      - 10.0.0.2/16
      dhcp4: no
      routes:
      - to: 0.0.0.0/0
        via: 10.0.0.1
    '''

    # language=YAML
    valid_open_wifi_cfg = '''
network:
  version: 2
  renderer: networkd
  wifis:
    wlan0:
      addresses:
      - 10.0.0.2/16
      dhcp4: no
      routes:
      - to: 0.0.0.0/0
        via: 10.0.0.1
      access-points:
        test-wifi: {}
    '''

    def _test_netplan_cfg(self,
                          expected: str,
                          to_test: Collection[_BaseNetplanIfaceCfg],
                          version: int = 2,
                          renderer: str = 'networkd') -> None:
        valid = yaml.safe_load(expected)
        test_netplan_cfg = NetplanConfig(
            version=version,
            renderer=renderer
        )

        for cfg in to_test:
            test_netplan_cfg.add_config(cfg)

        self.assertDictEqual(
            valid,
            test_netplan_cfg.to_netplan_dict(),
            msg=f'''
Expected:\n
{expected}

Got:\n
{test_netplan_cfg.to_netplan_yaml()}
'''
        )

    def test_eth_cfg(self) -> None:
        self._test_netplan_cfg(
            expected=self.valid_eth_cfg,
            to_test=[
                EthNetplanCfg(
                    interface='eth0',
                    ip_address=IPv4Interface('10.0.0.2/16'),
                    routes=(IPRoute(
                        to=IPv4Interface('0.0.0.0/0'),
                        via=IPv4Address('10.0.0.1')),
                    )
                )
            ]
        )

    def test_open_wifi_cfg(self) -> None:
        self._test_netplan_cfg(
            expected=self.valid_open_wifi_cfg,
            to_test=[
                WiFiNetplanCfg(
                    interface='wlan0',
                    ip_address=IPv4Interface('10.0.0.2/16'),
                    routes=(IPRoute(
                        to=IPv4Interface('0.0.0.0/0'),
                        via=IPv4Address('10.0.0.1')),
                    ),
                    ssid='test-wifi'
                )
            ]
        )
