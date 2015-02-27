# Copyright 2014
# The Cloudscaling Group, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock
from neutronclient.common import exceptions as neutron_exception

from ec2api.tests.unit import base
from ec2api.tests.unit import fakes
from ec2api.tests.unit import matchers
from ec2api.tests.unit import tools


class SubnetTestCase(base.ApiTestCase):

    def test_create_subnet(self):
        self.db_api.get_item_by_id.side_effect = (
                fakes.get_db_api_get_item_by_id({
                        fakes.ID_EC2_VPC_1: fakes.DB_VPC_1,
                        fakes.ID_EC2_ROUTE_TABLE_1: fakes.DB_ROUTE_TABLE_1}))
        self.db_api.add_item.side_effect = (
                fakes.get_db_api_add_item(fakes.ID_EC2_SUBNET_1))
        self.neutron.create_network.side_effect = (
                fakes.get_neutron_create('network', fakes.ID_OS_NETWORK_1,
                                         {'status': 'available'}))
        self.neutron.create_subnet.side_effect = (
                fakes.get_neutron_create('subnet', fakes.ID_OS_SUBNET_1))

        def check_response(resp):
            self.assertEqual(200, resp['http_status_code'])
            self.assertThat(fakes.EC2_SUBNET_1, matchers.DictMatches(
                    resp['subnet']))
            self.db_api.add_item.assert_called_once_with(
                    mock.ANY, 'subnet',
                    tools.purge_dict(fakes.DB_SUBNET_1, ('id',)))
            self.neutron.create_network.assert_called_once_with(
                    {'network': {}})
            self.neutron.update_network.assert_called_once_with(
                    fakes.ID_OS_NETWORK_1,
                    {'network': {'name': fakes.ID_EC2_SUBNET_1}})
            self.neutron.create_subnet.assert_called_once_with(
                    {'subnet': tools.purge_dict(fakes.OS_SUBNET_1,
                                                ('id', 'name'))})
            self.neutron.update_subnet.assert_called_once_with(
                    fakes.ID_OS_SUBNET_1,
                    {'subnet': {'name': fakes.ID_EC2_SUBNET_1}})
            self.neutron.add_interface_router.assert_called_once_with(
                    fakes.ID_OS_ROUTER_1,
                    {'subnet_id': fakes.ID_OS_SUBNET_1})

        resp = self.execute('CreateSubnet', {'VpcId': fakes.ID_EC2_VPC_1,
                                             'CidrBlock': fakes.CIDR_SUBNET_1})
        check_response(resp)

        self.neutron.reset_mock()
        self.db_api.reset_mock()

        resp = self.execute('CreateSubnet', {'VpcId': fakes.ID_EC2_VPC_1,
                                             'CidrBlock': fakes.CIDR_SUBNET_1,
                                             'AvailabilityZone': 'nova'})
        check_response(resp)

    def test_create_subnet_invalid_parameters(self):
        def check_response(resp, error_code):
            self.assertEqual(400, resp['http_status_code'])
            self.assertEqual(error_code, resp['Error']['Code'])
            self.assertEqual(0, self.neutron.create_network.call_count)
            self.assertEqual(0, self.neutron.create_subnet.call_count)
            self.assertEqual(0, self.neutron.add_interface_router.call_count)

            self.neutron.reset_mock()
            self.db_api.reset_mock()

        self.db_api.get_item_by_id.return_value = None
        resp = self.execute('CreateSubnet', {'VpcId': fakes.ID_EC2_VPC_1,
                                             'CidrBlock': fakes.CIDR_SUBNET_1})
        self.db_api.get_item_by_id.assert_called_once_with(mock.ANY,
                                                           fakes.ID_EC2_VPC_1)
        check_response(resp, 'InvalidVpcID.NotFound')

        self.db_api.get_item_by_id.return_value = fakes.DB_VPC_1
        resp = self.execute('CreateSubnet', {'VpcId': fakes.ID_EC2_VPC_1,
                                             'CidrBlock': 'invalid_cidr'})
        self.assertEqual(0, self.db_api.get_item_by_id.call_count)
        check_response(resp, 'InvalidParameterValue')

        resp = self.execute('CreateSubnet', {'VpcId': fakes.ID_EC2_VPC_1,
                                             'CidrBlock': '10.10.0.0/30'})
        self.assertEqual(0, self.db_api.get_item_by_id.call_count)
        check_response(resp, 'InvalidSubnet.Range')

        resp = self.execute('CreateSubnet', {'VpcId': fakes.ID_EC2_VPC_1,
                                             'CidrBlock': '10.20.0.0/24'})
        self.db_api.get_item_by_id.assert_called_once_with(mock.ANY,
                                                           fakes.ID_EC2_VPC_1)
        check_response(resp, 'InvalidSubnet.Range')

    def test_create_subnet_overlapped(self):
        self.db_api.get_item_by_id.side_effect = (
                fakes.get_db_api_get_item_by_id({
                        fakes.ID_EC2_VPC_1: fakes.DB_VPC_1,
                        fakes.ID_EC2_ROUTE_TABLE_1: fakes.DB_ROUTE_TABLE_1}))
        self.neutron.create_network.side_effect = (
                fakes.get_neutron_create('network', fakes.ID_OS_NETWORK_1,
                                         {'status': 'available'}))
        self.neutron.create_subnet.side_effect = (
                fakes.get_neutron_create('subnet', fakes.ID_OS_SUBNET_1))
        self.neutron.add_interface_router.side_effect = (
                neutron_exception.BadRequest())

        resp = self.execute('CreateSubnet', {'VpcId': fakes.ID_EC2_VPC_1,
                                             'CidrBlock': fakes.CIDR_SUBNET_1})
        self.assertEqual(400, resp['http_status_code'])
        self.assertEqual('InvalidSubnet.Conflict', resp['Error']['Code'])

    def test_create_subnet_overlimit(self):
        self.db_api.get_item_by_id.side_effect = (
                fakes.get_db_api_get_item_by_id({
                        fakes.ID_EC2_VPC_1: fakes.DB_VPC_1,
                        fakes.ID_EC2_ROUTE_TABLE_1: fakes.DB_ROUTE_TABLE_1}))
        self.neutron.create_network.side_effect = (
                fakes.get_neutron_create('network', fakes.ID_OS_NETWORK_1,
                                         {'status': 'available'}))
        self.neutron.create_subnet.side_effect = (
                fakes.get_neutron_create('subnet', fakes.ID_OS_SUBNET_1))

        def test_overlimit(func):
            self.neutron.reset_mock()
            saved_side_effect = func.side_effect
            func.side_effect = neutron_exception.OverQuotaClient

            resp = self.execute('CreateSubnet',
                                {'VpcId': fakes.ID_EC2_VPC_1,
                                 'CidrBlock': fakes.CIDR_SUBNET_1})

            self.assertEqual(400, resp['http_status_code'])
            self.assertEqual('SubnetLimitExceeded', resp['Error']['Code'])
            func.side_effect = saved_side_effect

        test_overlimit(self.neutron.create_network)
        test_overlimit(self.neutron.create_subnet)

    def test_create_subnet_rollback(self):
        self.db_api.get_item_by_id.side_effect = (
                fakes.get_db_api_get_item_by_id({
                        fakes.ID_EC2_VPC_1: fakes.DB_VPC_1,
                        fakes.ID_EC2_ROUTE_TABLE_1: fakes.DB_ROUTE_TABLE_1}))
        self.db_api.add_item.side_effect = (
                fakes.get_db_api_add_item(fakes.ID_EC2_SUBNET_1))
        self.neutron.create_network.side_effect = (
                fakes.get_neutron_create('network', fakes.ID_OS_NETWORK_1,
                                         {'status': 'available'}))
        self.neutron.create_subnet.side_effect = (
                fakes.get_neutron_create('subnet', fakes.ID_OS_SUBNET_1))
        self.neutron.update_network.side_effect = Exception()

        self.execute('CreateSubnet', {'VpcId': fakes.ID_EC2_VPC_1,
                                      'CidrBlock': fakes.CIDR_SUBNET_1})

        self.neutron.assert_has_calls([
            mock.call.remove_interface_router(
                fakes.ID_OS_ROUTER_1, {'subnet_id': fakes.ID_OS_SUBNET_1}),
            mock.call.delete_subnet(fakes.ID_OS_SUBNET_1),
            mock.call.delete_network(fakes.ID_OS_NETWORK_1)])
        self.db_api.delete_item.assert_called_once_with(
                mock.ANY, fakes.ID_EC2_SUBNET_1)

    def test_delete_subnet(self):
        self.db_api.get_item_by_id.side_effect = (
                fakes.get_db_api_get_item_by_id(
                        {fakes.ID_EC2_VPC_1: fakes.DB_VPC_1,
                         fakes.ID_EC2_SUBNET_1: fakes.DB_SUBNET_1}))
        self.neutron.show_subnet.return_value = (
                {'subnet': fakes.OS_SUBNET_1})
        self.db_api.get_items.return_value = []

        resp = self.execute('DeleteSubnet',
                            {'subnetId': fakes.ID_EC2_SUBNET_1})

        self.assertEqual(200, resp['http_status_code'])
        self.assertEqual(True, resp['return'])
        self.db_api.delete_item.assert_called_once_with(
                mock.ANY,
                fakes.ID_EC2_SUBNET_1)
        self.neutron.remove_interface_router.assert_called_once_with(
                fakes.ID_OS_ROUTER_1,
                {'subnet_id': fakes.ID_OS_SUBNET_1})
        self.neutron.delete_network.assert_called_once_with(
                fakes.ID_OS_NETWORK_1)
        self.assertTrue(
            self.neutron.mock_calls.index(
                mock.call.delete_network(fakes.ID_OS_NETWORK_1)) >
            self.neutron.mock_calls.index(
                mock.call.remove_interface_router(
                    fakes.ID_OS_ROUTER_1,
                    {'subnet_id': fakes.ID_OS_SUBNET_1})))

    def test_delete_subnet_inconsistent_os(self):
        self.db_api.get_item_by_id.side_effect = (
                fakes.get_db_api_get_item_by_id(
                        {fakes.ID_EC2_VPC_1: fakes.DB_VPC_1,
                         fakes.ID_EC2_SUBNET_1: fakes.DB_SUBNET_1}))
        self.db_api.get_items.return_value = []
        self.neutron.remove_interface_router.side_effect = (
                neutron_exception.NotFound())
        self.neutron.show_subnet.return_value = (
                {'subnet': fakes.OS_SUBNET_1})
        self.neutron.delete_network.side_effect = (
                neutron_exception.NetworkInUseClient())

        resp = self.execute('DeleteSubnet',
                            {'subnetId': fakes.ID_EC2_SUBNET_1})
        self.assertEqual(200, resp['http_status_code'])
        self.assertEqual(True, resp['return'])

        self.neutron.show_subnet.side_effect = neutron_exception.NotFound()

        resp = self.execute('DeleteSubnet',
                            {'subnetId': fakes.ID_EC2_SUBNET_1})
        self.assertEqual(200, resp['http_status_code'])
        self.assertEqual(True, resp['return'])

    def test_delete_subnet_invalid_parameters(self):
        self.db_api.get_item_by_id.return_value = None
        self.neutron.show_subnet.return_value = fakes.OS_SUBNET_1
        self.neutron.show_network.return_value = fakes.OS_NETWORK_1

        resp = self.execute('DeleteSubnet',
                            {'subnetId': fakes.ID_EC2_SUBNET_1})

        self.assertEqual(400, resp['http_status_code'])
        self.assertEqual('InvalidSubnetID.NotFound', resp['Error']['Code'])
        self.assertEqual(0, self.neutron.delete_network.call_count)
        self.assertEqual(0, self.neutron.delete_subnet.call_count)
        self.assertEqual(0, self.neutron.remove_interface_router.call_count)

    @mock.patch('ec2api.api.network_interface.describe_network_interfaces')
    def test_delete_subnet_not_empty(self, describe_network_interfaces):
        self.db_api.get_item_by_id.side_effect = (
                fakes.get_db_api_get_item_by_id(
                        {fakes.ID_EC2_VPC_1: fakes.DB_VPC_1,
                         fakes.ID_EC2_SUBNET_1: fakes.DB_SUBNET_1}))
        describe_network_interfaces.return_value = (
                {'networkInterfaceSet': [fakes.EC2_NETWORK_INTERFACE_1]})
        resp = self.execute('DeleteSubnet',
                            {'subnetId': fakes.ID_EC2_SUBNET_1})
        self.assertEqual(400, resp['http_status_code'])
        self.assertEqual('DependencyViolation', resp['Error']['Code'])

    def test_delete_subnet_rollback(self):
        self.db_api.get_item_by_id.side_effect = (
                fakes.get_db_api_get_item_by_id(
                        {fakes.ID_EC2_VPC_1: fakes.DB_VPC_1,
                         fakes.ID_EC2_SUBNET_1: fakes.DB_SUBNET_1}))
        self.neutron.show_subnet.side_effect = Exception()

        self.execute('DeleteSubnet', {'subnetId': fakes.ID_EC2_SUBNET_1})

        self.db_api.restore_item.assert_called_once_with(
                mock.ANY, 'subnet', fakes.DB_SUBNET_1)
        self.neutron.add_interface_router.assert_called_once_with(
                fakes.ID_OS_ROUTER_1, {'subnet_id': fakes.ID_OS_SUBNET_1})

    def test_describe_subnets(self):
        self.db_api.get_items.return_value = (
                [fakes.DB_SUBNET_1, fakes.DB_SUBNET_2])
        self.neutron.list_subnets.return_value = (
                {'subnets': [fakes.OS_SUBNET_1, fakes.OS_SUBNET_2]})
        self.neutron.list_networks.return_value = (
                {'networks': [fakes.OS_NETWORK_1, fakes.OS_NETWORK_2]})

        resp = self.execute('DescribeSubnets', {})
        self.assertEqual(200, resp['http_status_code'])
        self.assertThat(resp['subnetSet'],
                        matchers.ListMatches([fakes.EC2_SUBNET_1,
                                              fakes.EC2_SUBNET_2]))

        self.db_api.get_items_by_ids = tools.CopyingMock(
            return_value=[fakes.DB_SUBNET_2])
        resp = self.execute('DescribeSubnets',
                            {'SubnetId.1': fakes.ID_EC2_SUBNET_2})
        self.assertEqual(200, resp['http_status_code'])
        self.assertThat(resp['subnetSet'],
                        matchers.ListMatches([fakes.EC2_SUBNET_2]))
        self.db_api.get_items_by_ids.assert_called_once_with(
            mock.ANY, set([fakes.ID_EC2_SUBNET_2]))

        self.check_filtering(
            'DescribeSubnets', 'subnetSet',
            [
             # TODO(ft): support filtering by a number value # noqa
             # NOTE(ft): declare a constant for the count in fakes
             # ('available-ip-address-count', 253),
             ('cidr', fakes.CIDR_SUBNET_2),
             ('cidrBlock', fakes.CIDR_SUBNET_2),
             ('cidr-block', fakes.CIDR_SUBNET_2),
             ('subnet-id', fakes.ID_EC2_SUBNET_2),
             ('state', 'available'),
             ('vpc-id', fakes.ID_EC2_VPC_1)])
        self.check_tag_support(
            'DescribeSubnets', 'subnetSet',
            fakes.ID_EC2_SUBNET_2, 'subnetId')

    def test_describe_subnets_not_consistent_os_subnet(self):
        self.db_api.get_items.return_value = (
                [fakes.DB_SUBNET_1, fakes.DB_SUBNET_2])
        self.neutron.list_subnets.return_value = (
                {'subnets': [fakes.OS_SUBNET_2]})
        self.neutron.list_networks.return_value = (
                {'networks': [fakes.OS_NETWORK_1]})

        resp = self.execute('DescribeSubnets', {})
        self.assertEqual(200, resp['http_status_code'])
        self.assertEqual([], resp['subnetSet'])
