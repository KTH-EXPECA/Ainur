from contextlib import ExitStack

import click

from ainur.physical import PhysicalLayer
from ainur_utils.hosts import EDGE_HOST
from ainur_utils.resources import switch

AP_PORT = 5


@click.command()
def init_net():
    with ExitStack() as stack:
        # start phy layer
        phy_layer: PhysicalLayer = stack.enter_context(
            PhysicalLayer(hosts={}, radio_aps=[], radio_stas=[], switch=switch)
        )

        # hack to make vlan including AP and elrond
        switch_ports = [
            AP_PORT,
            EDGE_HOST.ethernets["enp4s0"].wire_spec.switch_port,
        ]
        phy_layer._switch.make_vlan(switch_ports, name="edgedroid_vlan")
        phy_layer._hosts = dict(elrond=EDGE_HOST)

        click.pause()


if __name__ == "__main__":
    init_net()
