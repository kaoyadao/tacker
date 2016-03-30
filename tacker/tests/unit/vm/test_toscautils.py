# Copyright 2016 - Nokia
# Licensed under the Apache License, Version 2.0 (the "License"); you may
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

import codecs
import os
import testtools
import yaml

from tacker.vm.tosca import utils as toscautils
from toscaparser.tosca_template import ToscaTemplate
from translator.hot.tosca_translator import TOSCATranslator


def _get_template(name):
    filename = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "infra_drivers/heat/data/", name)
    f = codecs.open(filename, encoding='utf-8', errors='strict')
    return f.read()


class TestToscaUtils(testtools.TestCase):
    tosca_openwrt = _get_template('test_tosca_openwrt.yaml')
    vnfd_dict = yaml.load(tosca_openwrt)
    toscautils.updateimports(vnfd_dict)
    tosca = ToscaTemplate(parsed_params={}, a_file=False,
                          yaml_dict_tpl=vnfd_dict)
    tosca_flavor = _get_template('test_tosca_flavor.yaml')

    def setUp(self):
        super(TestToscaUtils, self).setUp()

    def test_updateimport(self):
        importspath = os.path.abspath('./tacker/vm/tosca/lib/')
        file1 = importspath + '/tacker_defs.yaml'
        file2 = importspath + '/tacker_nfv_defs.yaml'
        expected_imports = [file1, file2]
        self.assertEqual(self.vnfd_dict['imports'], expected_imports)

    def test_get_mgmt_driver(self):
        expected_mgmt_driver = 'openwrt'
        mgmt_driver = toscautils.get_mgmt_driver(self.tosca)
        self.assertEqual(mgmt_driver, expected_mgmt_driver)

    def test_get_vdu_monitoring(self):
        expected_monitoring = {'vdus': {'VDU1': {'actions':
                                 [{'action': 'respawn',
                                   'trigger': 'failure'}],
                               'name': 'ping',
                               'parameters': {'count': '3',
                                              'interval': '10'}}}}
        monitoring = toscautils.get_vdu_monitoring(self.tosca)
        self.assertEqual(monitoring, expected_monitoring)

    def test_get_mgmt_ports(self):
        expected_mgmt_ports = {'mgmt_ip-VDU1': 'CP1'}
        mgmt_ports = toscautils.get_mgmt_ports(self.tosca)
        self.assertEqual(mgmt_ports, expected_mgmt_ports)

    def test_post_process_template(self):
        tosca2 = ToscaTemplate(parsed_params={}, a_file=False,
                          yaml_dict_tpl=self.vnfd_dict)
        toscautils.post_process_template(tosca2)
        invalidNodes = 0
        for nt in tosca2.nodetemplates:
            if (nt.type_definition.is_derived_from(toscautils.MONITORING) or
                nt.type_definition.is_derived_from(toscautils.FAILURE) or
                    nt.type_definition.is_derived_from(toscautils.PLACEMENT)):
                invalidNodes += 1

        self.assertEqual(invalidNodes, 0)

        deletedProperties = 0
        if nt.type in toscautils.delpropmap.keys():
            for prop in toscautils.delpropmap[nt.type]:
                for p in nt.get_properties_objects():
                    if prop == p.name:
                        deletedProperties += 1

        self.assertEqual(deletedProperties, 0)

        convertedProperties = 0
        if nt.type in toscautils.convert_prop:
            for prop in toscautils.convert_prop[nt.type].keys():
                for p in nt.get_properties_objects():
                    if prop == p.name:
                        convertedProperties += 1

        self.assertEqual(convertedProperties, 0)

    def test_post_process_heat_template(self):
        tosca1 = ToscaTemplate(parsed_params={}, a_file=False,
                          yaml_dict_tpl=self.vnfd_dict)
        toscautils.post_process_template(tosca1)
        translator = TOSCATranslator(tosca1, {})
        heat_template_yaml = translator.translate()
        expected_heat_tpl = _get_template('hot_tosca_openwrt.yaml')
        mgmt_ports = toscautils.get_mgmt_ports(self.tosca)
        heat_tpl = toscautils.post_process_heat_template(
            heat_template_yaml, mgmt_ports, {})

        heatdict = yaml.load(heat_tpl)
        expecteddict = yaml.load(expected_heat_tpl)
        self.assertEqual(heatdict, expecteddict)

    def test_findvdus(self):
        vdus = toscautils.findvdus(self.tosca)

        self.assertEqual(len(vdus), 1)

        for vdu in vdus:
            self.assertEqual(vdu.type_definition.is_derived_from(
                toscautils.TACKERVDU), True)

    def test_get_flavor_dict(self):
        vnfd_dict = yaml.load(self.tosca_flavor)
        toscautils.updateimports(vnfd_dict)
        tosca = ToscaTemplate(a_file=False, yaml_dict_tpl=vnfd_dict)
        expected_flavor_dict = {
            "VDU1": {
                "vcpus": 2,
                "disk": 10,
                "ram": 512
            }
        }
        actual_flavor_dict = toscautils.get_flavor_dict(tosca)
        self.assertEqual(expected_flavor_dict, actual_flavor_dict)

    def test_add_resources_tpl_for_flavor(self):
        dummy_heat_dict = yaml.load(_get_template(
            'hot_flavor_and_capabilities.yaml'))
        expected_dict = yaml.load(_get_template('hot_flavor.yaml'))
        dummy_heat_res = {
            "flavor": {
                "VDU1": {
                    "vcpus": 2,
                    "ram": 512,
                    "disk": 10
                }
            }
        }
        toscautils.add_resources_tpl(dummy_heat_dict, dummy_heat_res)
        self.assertEqual(dummy_heat_dict, expected_dict)

    def test_get_flavor_dict_extra_specs_all_numa_count(self):
        tosca_fes_all_numa_count = _get_template(
            'tosca_flavor_all_numa_count.yaml')
        vnfd_dict = yaml.load(tosca_fes_all_numa_count)
        toscautils.updateimports(vnfd_dict)
        tosca = ToscaTemplate(a_file=False, yaml_dict_tpl=vnfd_dict)
        expected_flavor_dict = {
            "VDU1": {
                "vcpus": 8,
                "disk": 10,
                "ram": 4096,
                "extra_specs": {
                    'hw:cpu_policy': 'dedicated', 'hw:mem_page_size': 'any',
                    'hw:cpu_sockets': 2, 'hw:cpu_threads': 2,
                    'hw:numa_nodes': 2, 'hw:cpu_cores': 2,
                    'hw:cpu_threads_policy': 'avoid'
                }
            }
        }
        actual_flavor_dict = toscautils.get_flavor_dict(tosca)
        self.assertEqual(expected_flavor_dict, actual_flavor_dict)

    def test_tacker_conf_heat_extra_specs_all_numa_count(self):
        tosca_fes_all_numa_count = _get_template(
            'tosca_flavor_all_numa_count.yaml')
        vnfd_dict = yaml.load(tosca_fes_all_numa_count)
        toscautils.updateimports(vnfd_dict)
        tosca = ToscaTemplate(a_file=False, yaml_dict_tpl=vnfd_dict)
        expected_flavor_dict = {
            "VDU1": {
                "vcpus": 8,
                "disk": 10,
                "ram": 4096,
                "extra_specs": {
                    'hw:cpu_policy': 'dedicated', 'hw:mem_page_size': 'any',
                    'hw:cpu_sockets': 2, 'hw:cpu_threads': 2,
                    'hw:numa_nodes': 2, 'hw:cpu_cores': 2,
                    'hw:cpu_threads_policy': 'avoid',
                    'aggregate_instance_extra_specs:nfv': 'true'
                }
            }
        }
        actual_flavor_dict = toscautils.get_flavor_dict(
            tosca, {"aggregate_instance_extra_specs:nfv": "true"})
        self.assertEqual(expected_flavor_dict, actual_flavor_dict)

    def test_add_resources_tpl_for_image(self):
        dummy_heat_dict = yaml.load(_get_template(
            'hot_image_before_processed_image.yaml'))
        expected_dict = yaml.load(_get_template(
            'hot_image_after_processed_image.yaml'))
        dummy_heat_res = {
            "image": {
                "VDU1": {
                    "location": "http://URL/v1/openwrt.qcow2",
                    "container_format": "bare",
                    "disk_format": "raw"
                }
            }
        }
        toscautils.add_resources_tpl(dummy_heat_dict, dummy_heat_res)
        self.assertEqual(dummy_heat_dict, expected_dict)