# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
# Copyright (c) 2012 X.commerce, a business unit of eBay Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from __future__ import absolute_import

from django.conf import settings
from django.test.utils import override_settings

import mock
from novaclient import api_versions
from novaclient import exceptions as nova_exceptions
from novaclient.v2 import flavor_access as nova_flavor_access
from novaclient.v2 import servers

from horizon import exceptions as horizon_exceptions
from openstack_dashboard import api
from openstack_dashboard.test import helpers as test


class ServerWrapperTests(test.TestCase):

    use_mox = False

    def test_get_base_attribute(self):
        server = api.nova.Server(self.servers.first(), self.request)
        self.assertEqual(self.servers.first().id, server.id)

    @mock.patch.object(api.glance, 'image_get')
    def test_image_name(self, mock_image_get):
        image = self.images.first()
        mock_image_get.return_value = image

        server = api.nova.Server(self.servers.first(), self.request)
        self.assertEqual(image.name, server.image_name)
        mock_image_get.assert_called_once_with(test.IsHttpRequest(), image.id)

    @mock.patch.object(api.glance, 'image_get')
    def test_image_name_no_glance_service(self, mock_image_get):
        server = self.servers.first()
        exc_catalog = horizon_exceptions.ServiceCatalogException('image')
        mock_image_get.side_effect = exc_catalog

        server = api.nova.Server(server, self.request)
        self.assertIsNone(server.image_name)
        mock_image_get.assert_called_once_with(test.IsHttpRequest(),
                                               server.image['id'])


class ComputeApiTests(test.APIMockTestCase):

    def _mock_current_version(self, mock_novaclient, version,
                              min_version=None):
        ver = mock.Mock()
        ver.min_version = min_version or '2.1'
        ver.version = version
        mock_novaclient.versions.get_current.return_value = ver
        # To handle upgrade_api
        self.novaclient.api_version = api_versions.APIVersion(version)

    def test_server_reboot(self):
        server = self.servers.first()
        HARDNESS = servers.REBOOT_HARD

        novaclient = self.stub_novaclient()
        novaclient.servers.reboot.return_value = None

        ret_val = api.nova.server_reboot(self.request, server.id)

        self.assertIsNone(ret_val)
        novaclient.servers.reboot.assert_called_once_with(
            server.id, HARDNESS)

    def test_server_soft_reboot(self):
        server = self.servers.first()
        HARDNESS = servers.REBOOT_SOFT

        novaclient = self.stub_novaclient()
        novaclient.servers.reboot.return_value = None

        ret_val = api.nova.server_reboot(self.request, server.id, HARDNESS)

        self.assertIsNone(ret_val)
        novaclient.servers.reboot.assert_called_once_with(
            server.id, HARDNESS)

    def test_server_vnc_console(self):
        server = self.servers.first()
        console = self.servers.vnc_console_data
        console_type = console["console"]["type"]

        novaclient = self.stub_novaclient()
        novaclient.servers.get_vnc_console.return_value = console

        ret_val = api.nova.server_vnc_console(self.request,
                                              server.id,
                                              console_type)

        self.assertIsInstance(ret_val, api.nova.VNCConsole)
        novaclient.servers.get_vnc_console.assert_called_once_with(
            server.id, console_type)

    def test_server_spice_console(self):
        server = self.servers.first()
        console = self.servers.spice_console_data
        console_type = console["console"]["type"]

        novaclient = self.stub_novaclient()
        novaclient.servers.get_spice_console.return_value = console

        ret_val = api.nova.server_spice_console(self.request,
                                                server.id,
                                                console_type)
        self.assertIsInstance(ret_val, api.nova.SPICEConsole)
        novaclient.servers.get_spice_console.assert_called_once_with(
            server.id, console_type)

    def test_server_rdp_console(self):
        server = self.servers.first()
        console = self.servers.rdp_console_data
        console_type = console["console"]["type"]

        novaclient = self.stub_novaclient()
        novaclient.servers.get_rdp_console.return_value = console

        ret_val = api.nova.server_rdp_console(self.request,
                                              server.id,
                                              console_type)
        self.assertIsInstance(ret_val, api.nova.RDPConsole)
        novaclient.servers.get_rdp_console.assert_called_once_with(
            server.id, console_type)

    def test_server_mks_console(self):
        server = self.servers.first()
        console = self.servers.mks_console_data
        console_type = console["remote_console"]["type"]

        novaclient = self.stub_novaclient()
        self._mock_current_version(novaclient, '2.53')
        novaclient.servers.get_mks_console.return_value = console

        ret_val = api.nova.server_mks_console(self.request,
                                              server.id,
                                              console_type)
        self.assertIsInstance(ret_val, api.nova.MKSConsole)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.servers.get_mks_console.assert_called_once_with(
            server.id, console_type)

    def test_server_list(self):
        servers = self.servers.list()

        novaclient = self.stub_novaclient()
        self._mock_current_version(novaclient, '2.40')
        novaclient.servers.list.return_value = servers

        ret_val, has_more = api.nova.server_list(
            self.request,
            search_opts={'all_tenants': True})
        for server in ret_val:
            self.assertIsInstance(server, api.nova.Server)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.servers.list.assert_called_once_with(
            True, {'all_tenants': True})

    def test_server_list_pagination(self):
        page_size = getattr(settings, 'API_RESULT_PAGE_SIZE', 20)
        servers = self.servers.list()
        novaclient = self.stub_novaclient()
        self._mock_current_version(novaclient, '2.45')
        novaclient.servers.list.return_value = servers

        ret_val, has_more = api.nova.server_list(self.request,
                                                 {'marker': None,
                                                  'paginate': True,
                                                  'all_tenants': True})
        for server in ret_val:
            self.assertIsInstance(server, api.nova.Server)
        self.assertFalse(has_more)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.servers.list.assert_called_once_with(
            True,
            {'all_tenants': True,
             'marker': None,
             'limit': page_size + 1})

    @override_settings(API_RESULT_PAGE_SIZE=1)
    def test_server_list_pagination_more(self):
        page_size = getattr(settings, 'API_RESULT_PAGE_SIZE', 1)
        servers = self.servers.list()
        novaclient = self.stub_novaclient()
        self._mock_current_version(novaclient, '2.45')
        novaclient.servers.list.return_value = servers[:page_size + 1]

        ret_val, has_more = api.nova.server_list(self.request,
                                                 {'marker': None,
                                                  'paginate': True,
                                                  'all_tenants': True})

        for server in ret_val:
            self.assertIsInstance(server, api.nova.Server)
        self.assertEqual(page_size, len(ret_val))
        self.assertTrue(has_more)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.servers.list.assert_called_once_with(
            True,
            {'all_tenants': True,
             'marker': None,
             'limit': page_size + 1})

    def test_usage_get(self):
        novaclient = self.stub_novaclient()
        self._mock_current_version(novaclient, '2.1')
        novaclient.usages.get.return_value = self.usages.first()

        ret_val = api.nova.usage_get(self.request, self.tenant.id,
                                     'start', 'end')

        self.assertIsInstance(ret_val, api.nova.NovaUsage)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.usage.get.assert_called_once_with(
            self.tenant.id, 'start', 'end')

    def test_usage_get_paginated(self):
        novaclient = self.stub_novaclient()
        self._mock_current_version(novaclient, '2.40')
        novaclient.usage.get.side_effect = [
            self.usages.first(),
            {},
        ]

        ret_val = api.nova.usage_get(self.request, self.tenant.id,
                                     'start', 'end')

        self.assertIsInstance(ret_val, api.nova.NovaUsage)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.usage.get.assert_has_calls([
            mock.call(self.tenant.id, 'start', 'end'),
            mock.call(self.tenant.id, 'start', 'end',
                      marker=u'063cf7f3-ded1-4297-bc4c-31eae876cc93'),
        ])

    def test_usage_list(self):
        usages = self.usages.list()

        novaclient = self.stub_novaclient()
        self._mock_current_version(novaclient, '2.1')
        novaclient.usage.list.return_value = usages

        ret_val = api.nova.usage_list(self.request, 'start', 'end')

        for usage in ret_val:
            self.assertIsInstance(usage, api.nova.NovaUsage)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.usage.list.assert_called_once_with('start', 'end', True)

    def test_usage_list_paginated(self):
        usages = self.usages.list()

        novaclient = self.stub_novaclient()
        self._mock_current_version(novaclient, '2.40')
        novaclient.usage.list.side_effect = [
            usages,
            {},
        ]

        ret_val = api.nova.usage_list(self.request, 'start', 'end')

        for usage in ret_val:
            self.assertIsInstance(usage, api.nova.NovaUsage)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.usage.list.assert_has_calls([
            mock.call('start', 'end', True),
            mock.call('start', 'end', True,
                      marker=u'063cf7f3-ded1-4297-bc4c-31eae876cc93'),
        ])

    def test_server_get(self):
        server = self.servers.first()

        novaclient = self.stub_novaclient()
        self._mock_current_version(novaclient, '2.45')
        novaclient.servers.get.return_value = server

        ret_val = api.nova.server_get(self.request, server.id)
        self.assertIsInstance(ret_val, api.nova.Server)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.servers.get.assert_called_once_with(server.id)

    def test_server_metadata_update(self):
        server = self.servers.first()
        metadata = {'foo': 'bar'}

        novaclient = self.stub_novaclient()
        novaclient.servers.set_meta.return_value = None

        ret_val = api.nova.server_metadata_update(self.request,
                                                  server.id,
                                                  metadata)
        self.assertIsNone(ret_val)
        novaclient.servers.set_meta.assert_called_once_with(server.id,
                                                            metadata)

    def test_server_metadata_delete(self):
        server = self.servers.first()
        keys = ['a', 'b']

        novaclient = self.stub_novaclient()
        novaclient.servers.delete_meta.return_value = None

        ret_val = api.nova.server_metadata_delete(self.request,
                                                  server.id,
                                                  keys)
        self.assertIsNone(ret_val)
        novaclient.servers.delete_meta.assert_called_once_with(server.id, keys)

    def _test_absolute_limits(self, values, expected_results):
        limits = mock.Mock()
        limits.absolute = []
        for key, val in values.items():
            limit = mock.Mock()
            limit.name = key
            limit.value = val
            limits.absolute.append(limit)

        novaclient = self.stub_novaclient()
        novaclient.limits.get.return_value = limits

        ret_val = api.nova.tenant_absolute_limits(self.request, reserved=True)

        for key in expected_results.keys():
            self.assertEqual(expected_results[key], ret_val[key])
        novaclient.limits.get.assert_called_once_with(reserved=True,
                                                      tenant_id=None)

    def test_absolute_limits_handle_unlimited(self):
        values = {"maxTotalCores": -1, "maxTotalInstances": 10}
        expected_results = {"maxTotalCores": float("inf"),
                            "maxTotalInstances": 10}
        self._test_absolute_limits(values, expected_results)

    def test_absolute_limits_negative_used_workaround(self):
        values = {"maxTotalCores": -1,
                  "maxTotalInstances": 10,
                  "totalInstancesUsed": -1,
                  "totalCoresUsed": -1,
                  "totalRAMUsed": -2048,
                  "totalSecurityGroupsUsed": 1,
                  "totalFloatingIpsUsed": 0,
                  }
        expected_results = {"maxTotalCores": float("inf"),
                            "maxTotalInstances": 10,
                            "totalInstancesUsed": 0,
                            "totalCoresUsed": 0,
                            "totalRAMUsed": 0,
                            "totalSecurityGroupsUsed": 1,
                            "totalFloatingIpsUsed": 0,
                            }
        self._test_absolute_limits(values, expected_results)

    def test_cold_migrate_host_succeed(self):
        hypervisor = self.hypervisors.first()
        novaclient = self.stub_novaclient()
        novaclient.hypervisors.search.return_value = [hypervisor]
        novaclient.servers.migrate.return_value = None

        ret_val = api.nova.migrate_host(self.request, "host", False, True,
                                        True)

        self.assertTrue(ret_val)
        novaclient.hypervisors.search.assert_called_once_with('host', True)
        novaclient.servers.migrate.assert_called_once_with('test_uuid')

    def test_cold_migrate_host_fails(self):
        hypervisor = self.hypervisors.first()
        novaclient = self.stub_novaclient()
        novaclient.hypervisors.search.return_value = [hypervisor]
        novaclient.servers.migrate.side_effect = \
            nova_exceptions.ClientException(404)

        self.assertRaises(nova_exceptions.ClientException,
                          api.nova.migrate_host,
                          self.request, "host", False, True, True)
        novaclient.hypervisors.search.assert_called_once_with('host', True)
        novaclient.servers.migrate.assert_called_once_with('test_uuid')

    def test_live_migrate_host_with_active_vm(self):
        hypervisor = self.hypervisors.first()
        server = self.servers.first()
        novaclient = self.stub_novaclient()
        server_uuid = hypervisor.servers[0]["uuid"]

        self._mock_current_version(novaclient, '2.45')
        novaclient.hypervisors.search.return_value = [hypervisor]
        novaclient.servers.get.return_value = server
        novaclient.servers.live_migrate.return_value = None

        ret_val = api.nova.migrate_host(self.request, "host", True, True,
                                        True)

        self.assertTrue(ret_val)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.hypervisors.search.assert_called_once_with('host', True)
        novaclient.servers.get.assert_called_once_with(server_uuid)
        novaclient.servers.live_migrate.assert_called_once_with(
            server_uuid, None, True, True)

    def test_live_migrate_host_with_paused_vm(self):
        hypervisor = self.hypervisors.first()
        server = self.servers.list()[3]
        novaclient = self.stub_novaclient()
        server_uuid = hypervisor.servers[0]["uuid"]

        self._mock_current_version(novaclient, '2.45')
        novaclient.hypervisors.search.return_value = [hypervisor]
        novaclient.servers.get.return_value = server
        novaclient.servers.live_migrate.return_value = None

        ret_val = api.nova.migrate_host(self.request, "host", True, True, True)

        self.assertTrue(ret_val)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.hypervisors.search.assert_called_once_with('host', True)
        novaclient.servers.get.assert_called_once_with(server_uuid)
        novaclient.servers.live_migrate.assert_called_once_with(
            server_uuid, None, True, True)

    def test_live_migrate_host_without_running_vm(self):
        hypervisor = self.hypervisors.first()
        server = self.servers.list()[1]
        novaclient = self.stub_novaclient()
        server_uuid = hypervisor.servers[0]["uuid"]

        self._mock_current_version(novaclient, '2.45')
        novaclient.hypervisors.search.return_value = [hypervisor]
        novaclient.servers.get.return_value = server
        novaclient.servers.migrate.return_value = None

        ret_val = api.nova.migrate_host(self.request, "host", True, True, True)

        self.assertTrue(ret_val)
        novaclient.versions.get_current.assert_called_once_with()
        novaclient.hypervisors.search.assert_called_once_with('host', True)
        novaclient.servers.get.assert_called_once_with(server_uuid)
        novaclient.servers.migrate.assert_called_once_with(server_uuid)

    """Flavor Tests"""

    def test_flavor_list_no_extras(self):
        flavors = self.flavors.list()
        novaclient = self.stub_novaclient()
        novaclient.flavors.list.return_value = flavors

        api_flavors = api.nova.flavor_list(self.request)

        self.assertEqual(len(flavors), len(api_flavors))
        novaclient.flavors.list.assert_called_once_with(is_public=True)

    def test_flavor_get_no_extras(self):
        flavor = self.flavors.list()[1]
        novaclient = self.stub_novaclient()
        novaclient.flavors.get.return_value = flavor

        api_flavor = api.nova.flavor_get(self.request, flavor.id)

        self.assertEqual(api_flavor.id, flavor.id)
        novaclient.flavors.get.assert_called_once_with(flavor.id)

    def _test_flavor_list_paged(self, reversed_order=False, paginate=True):
        page_size = getattr(settings, 'API_RESULT_PAGE_SIZE', 20)
        flavors = self.flavors.list()
        order = 'asc' if reversed_order else 'desc'
        novaclient = self.stub_novaclient()
        novaclient.flavors.list.return_value = flavors

        api_flavors, has_more, has_prev = api.nova.flavor_list_paged(
            self.request, True, False, None, paginate=paginate,
            reversed_order=reversed_order)

        for flavor in api_flavors:
            self.assertIsInstance(flavor, type(flavors[0]))
        self.assertFalse(has_more)
        self.assertFalse(has_prev)
        if paginate:
            novaclient.flavors.list.assert_called_once_with(
                is_public=True, marker=None, limit=page_size + 1,
                sort_key='name', sort_dir=order)
        else:
            novaclient.flavors.list.assert_called_once_with(
                is_public=True)

    @override_settings(API_RESULT_PAGE_SIZE=1)
    def test_flavor_list_pagination_more_and_prev(self):
        page_size = getattr(settings, 'API_RESULT_PAGE_SIZE', 1)
        flavors = self.flavors.list()
        marker = flavors[0].id
        novaclient = self.stub_novaclient()
        novaclient.flavors.list.return_value = flavors[1:page_size + 2]

        api_flavors, has_more, has_prev = api.nova\
                                             .flavor_list_paged(
                                                 self.request,
                                                 True,
                                                 False,
                                                 marker,
                                                 paginate=True)

        for flavor in api_flavors:
            self.assertIsInstance(flavor, type(flavors[0]))
        self.assertEqual(page_size, len(api_flavors))
        self.assertTrue(has_more)
        self.assertTrue(has_prev)
        novaclient.flavors.list.assert_called_once_with(
            is_public=True, marker=marker, limit=page_size + 1,
            sort_key='name', sort_dir='desc')

    def test_flavor_list_paged_default_order(self):
        self._test_flavor_list_paged()

    def test_flavor_list_paged_reversed_order(self):
        self._test_flavor_list_paged(reversed_order=True)

    def test_flavor_list_paged_paginate_false(self):
        self._test_flavor_list_paged(paginate=False)

    def test_flavor_create(self):
        flavor = self.flavors.first()

        novaclient = self.stub_novaclient()
        novaclient.flavors.create.return_value = flavor

        api_flavor = api.nova.flavor_create(self.request,
                                            flavor.name,
                                            flavor.ram,
                                            flavor.vcpus,
                                            flavor.disk)

        self.assertIsInstance(api_flavor, type(flavor))
        self.assertEqual(flavor.name, api_flavor.name)
        self.assertEqual(flavor.ram, api_flavor.ram)
        self.assertEqual(flavor.vcpus, api_flavor.vcpus)
        self.assertEqual(flavor.disk, api_flavor.disk)
        self.assertEqual(0, api_flavor.ephemeral)
        self.assertEqual(0, api_flavor.swap)
        self.assertTrue(api_flavor.is_public)
        self.assertEqual(1, api_flavor.rxtx_factor)

        novaclient.flavors.create.assert_called_once_with(
            flavor.name, flavor.ram, flavor.vcpus, flavor.disk,
            flavorid='auto', ephemeral=0, swap=0, is_public=True,
            rxtx_factor=1)

    def test_flavor_delete(self):
        flavor = self.flavors.first()
        novaclient = self.stub_novaclient()
        novaclient.flavors.delete.return_value = None

        api_val = api.nova.flavor_delete(self.request, flavor.id)

        self.assertIsNone(api_val)
        novaclient.flavors.delete.assert_called_once_with(flavor.id)

    def test_flavor_access_list(self):
        flavor_access = self.flavor_access.list()
        flavor = [f for f in self.flavors.list() if f.id ==
                  flavor_access[0].flavor_id][0]

        novaclient = self.stub_novaclient()
        novaclient.flavor_access.list.return_value = flavor_access

        api_flavor_access = api.nova.flavor_access_list(self.request, flavor)

        self.assertEqual(len(flavor_access), len(api_flavor_access))
        for access in api_flavor_access:
            self.assertIsInstance(access, nova_flavor_access.FlavorAccess)
            self.assertEqual(access.flavor_id, flavor.id)
        novaclient.flavor_access.list.assert_called_once_with(flavor=flavor)

    def test_add_tenant_to_flavor(self):
        flavor_access = [self.flavor_access.first()]
        flavor = [f for f in self.flavors.list() if f.id ==
                  flavor_access[0].flavor_id][0]
        tenant = [t for t in self.tenants.list() if t.id ==
                  flavor_access[0].tenant_id][0]
        novaclient = self.stub_novaclient()
        novaclient.flavor_access.add_tenant_access.return_value = flavor_access

        api_flavor_access = api.nova.add_tenant_to_flavor(self.request,
                                                          flavor,
                                                          tenant)
        self.assertIsInstance(api_flavor_access, list)
        self.assertEqual(len(flavor_access), len(api_flavor_access))

        for access in api_flavor_access:
            self.assertEqual(access.flavor_id, flavor.id)
            self.assertEqual(access.tenant_id, tenant.id)

        novaclient.flavor_access.add_tenant_access.assert_called_once_with(
            flavor=flavor, tenant=tenant)

    def test_remove_tenant_from_flavor(self):
        flavor_access = [self.flavor_access.first()]
        flavor = [f for f in self.flavors.list() if f.id ==
                  flavor_access[0].flavor_id][0]
        tenant = [t for t in self.tenants.list() if t.id ==
                  flavor_access[0].tenant_id][0]

        novaclient = self.stub_novaclient()
        novaclient.flavor_access.remove_tenant_access.return_value = []

        api_val = api.nova.remove_tenant_from_flavor(self.request,
                                                     flavor,
                                                     tenant)

        self.assertEqual(len(api_val), len([]))
        self.assertIsInstance(api_val, list)
        novaclient.flavor_access.remove_tenant_access.assert_called_once_with(
            flavor=flavor, tenant=tenant)

    def test_server_group_list(self):
        server_groups = self.server_groups.list()

        novaclient = self.stub_novaclient()
        novaclient.server_groups.list.return_value = server_groups

        ret_val = api.nova.server_group_list(self.request)

        self.assertIsInstance(ret_val, list)
        self.assertEqual(len(ret_val), len(server_groups))
        novaclient.server_groups.list.assert_called_once_with()
