#
# Copyright (c) 2019-2020 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

from contextlib import contextmanager

from libnmstate import nm
from libnmstate.schema import Interface
from libnmstate.schema import VXLAN

from ..testlib import statelib
from .testlib import main_context


def test_create_and_remove_vxlan(eth1_up, nm_plugin):
    vxlan_desired_state = _create_vxlan_state(eth1_up)
    with _vxlan_interface(nm_plugin.context, vxlan_desired_state):
        vxlan_name = _vxlan_ifname(vxlan_desired_state)
        vxlan_current_state = _get_vxlan_current_state(vxlan_name)
        assert vxlan_desired_state == vxlan_current_state

    assert not _get_vxlan_current_state(vxlan_name)


def test_read_destination_port_from_libnm(eth1_up, nm_plugin):
    vxlan_desired_state = _create_vxlan_state(eth1_up)
    with _vxlan_interface(nm_plugin.context, vxlan_desired_state):
        vxlan_name = _vxlan_ifname(vxlan_desired_state)
        vxlan_device = _get_vxlan_device(nm_plugin.context, vxlan_name)
        assert vxlan_device is not None
        obtained_destination_port = vxlan_device.props.dst_port
        expected_destination_port = vxlan_desired_state[VXLAN.CONFIG_SUBTREE][
            VXLAN.DESTINATION_PORT
        ]
        assert obtained_destination_port == expected_destination_port


def _create_vxlan_state(eth1_up):
    ifname = eth1_up[Interface.KEY][0][Interface.NAME]
    return {
        VXLAN.CONFIG_SUBTREE: {
            VXLAN.ID: 201,
            VXLAN.BASE_IFACE: ifname,
            VXLAN.REMOTE: "192.168.1.18",
            VXLAN.DESTINATION_PORT: 4789,
        }
    }


@contextmanager
def _vxlan_interface(ctx, state):
    con_profile = _create_vxlan(ctx, state)
    try:
        yield state
    finally:
        _delete_vxlan(ctx, con_profile)


def _create_vxlan(ctx, vxlan_desired_state):
    ifname = _vxlan_ifname(vxlan_desired_state)
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create(
        con_name=ifname,
        iface_name=ifname,
        iface_type=nm.common.NM.SETTING_VXLAN_SETTING_NAME,
    )
    vxlan_setting = nm.vxlan.create_setting(
        vxlan_desired_state, base_con_profile=None
    )
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)
    con_profile = nm.profile.NmProfile(ctx, True)
    con_profile._simple_conn = nm.connection.create_new_simple_connection(
        (con_setting.setting, vxlan_setting, ipv4_setting, ipv6_setting)
    )
    with main_context(ctx):
        con_profile._add()
        ctx.wait_all_finish()
        con_profile.activate()

    return con_profile


def _delete_vxlan(ctx, con_profile):
    with main_context(ctx):
        nm.device.deactivate(ctx, con_profile.nmdev)
        con_profile.delete()
        nm.device.delete_device(ctx, con_profile.nmdev)


def _get_vxlan_current_state(ifname):
    state = statelib.show_only((ifname,))
    vxlan_state = {}
    if state[Interface.KEY]:
        iface_state = state[Interface.KEY][0]
        vxlan_state = {VXLAN.CONFIG_SUBTREE: iface_state[VXLAN.CONFIG_SUBTREE]}

    return vxlan_state


def _get_vxlan_device(context, ifname):
    dev = context.get_nm_dev(ifname)
    return dev


def _vxlan_ifname(state):
    return (
        state[VXLAN.CONFIG_SUBTREE][VXLAN.BASE_IFACE]
        + "."
        + str(state[VXLAN.CONFIG_SUBTREE][VXLAN.ID])
    )
