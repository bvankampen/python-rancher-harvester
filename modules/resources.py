from .utils import get_value, format_k8s_value

# import yaml

import logging

logger = logging.getLogger(__name__)

class Resources:

    def __init__(self, config, kubernetes):
        self.config = config
        self.kubernetes = kubernetes
        # these are expensive call so load them once and then itterate and filter in code
        self.available_pcidevices_all = self.kubernetes.list_cluster(
        "devices.harvesterhci.io",
        "v1beta1",
        "pcidevices",
        )
        self.pcideviceclaims_all = self.kubernetes.list_cluster(
        "devices.harvesterhci.io",
        "v1beta1",
        "pcideviceclaims",
        )

    def get_available_pcidevices(self, node):
        result = []
        for device in self.available_pcidevices_all["items"]:
            if device["metadata"]["labels"]["nodename"] == node:
                for resource_class in self.config["resource_definitions"]:
                    for resource_name in self.config["resource_definitions"][resource_class]:
                        if resource_name == device["status"]["resourceName"]:
                            if self.is_pcidevice_available(node, device["metadata"]["name"]):
                                result.append(
                                {
                                    "name": device["metadata"]["name"],
                                    "address": device["status"]["address"],
                                    "deviceName": device["status"]["resourceName"],
                                    "usedBy": ""
                                })
        return result

    def is_pcidevice_available(self,node, name):
        for device in self.pcideviceclaims_all["items"]:
            if device["spec"]["nodeName"] == node and device["metadata"]["name"] == name:
                return True
        return False

    def get_node_resources(self, node, status_data, values):
        data = {
            "capacity": {},
            "allocatable": {},
        }
        for value in values:
            data["capacity"][value] = format_k8s_value(
                value, get_value(status_data.capacity, value)
            )
            data["allocatable"][value] = format_k8s_value(
                value, get_value(status_data.allocatable, value)
            )
        data["capacity"]["vm"]= int(status_data.capacity["pods"])
        data["allocatable"]["vm"] = int(status_data.capacity["pods"]) - self.get_pod_count(node)
        return data

    def get_virtualmachine_instances(self, node=None):
        label_selector = ""
        if node is not None:
           label_selector = f"kubevirt.io/nodeName={node}"
        return self.kubernetes.list(
            "kubevirt.io",
            "v1",
            "virtualmachineinstances",
            label_selector
        )

    def count_pcidevices(self, used_pcidevices_total, pcidevices):
        used_pcidevices={}
        for resource_class in self.config["resource_definitions"]:
            if resource_class not in used_pcidevices_total:
                used_pcidevices_total[resource_class] = 0;
            if resource_class not in used_pcidevices:
                used_pcidevices[resource_class] = 0
            for pcidevice in pcidevices:
                if pcidevice["deviceName"] in self.config["resource_definitions"][resource_class]:
                    used_pcidevices_total[resource_class] += 1
                    used_pcidevices[resource_class] += 1
        return used_pcidevices_total, used_pcidevices

    def get_virtualmachine_resources_by_node(self, node,pcidevices_all):
        vms = {}
        used_pcidevices_total = {}
        used_resources_total = {}
        instances = self.get_virtualmachine_instances(node)
        for instance in instances["items"]:
            if "hostDevices" in instance["spec"]["domain"]["devices"]:
                used_pcidevices_total, used_pcidevices = self.count_pcidevices(used_pcidevices_total, instance["spec"]["domain"]["devices"]["hostDevices"])
                pcidevices = instance["spec"]["domain"]["devices"]["hostDevices"]
                for pcidevice in pcidevices:
                    for i, pcidevice_all in enumerate(pcidevices_all):
                        if pcidevice["name"] == pcidevice_all["name"]:
                            pcidevices_all[i]["usedBy"] = instance["metadata"]["name"]
            else:
                pcidevices = []
                used_pcidevices = {}
            vms[instance["metadata"]["name"]] = {
                "cpu": format_k8s_value("cpu", instance["spec"]["domain"]["cpu"]["cores"]),
                "memory": format_k8s_value("memory",instance["spec"]["domain"]["memory"]["guest"]),
                "pcidevices": pcidevices
            }
            used_resources_total = self.add_totals(
                used_resources_total, {
                "cpu": format_k8s_value("cpu", instance["spec"]["domain"]["cpu"]["cores"]),
                "memory": format_k8s_value("memory",instance["spec"]["domain"]["memory"]["guest"])})
            for used_pcidevice in used_pcidevices:
                vms[instance["metadata"]["name"]][used_pcidevice] = used_pcidevices[used_pcidevice]

        used_resources_total["vm"] = len(vms)

        return used_resources_total, used_pcidevices_total, pcidevices_all, vms

    def add_totals(self, total_values, values):
        if total_values == {}:
            for key in values:
                total_values[key] = values[key]
        else:
            for key in total_values:
                if key in values:
                    total_values[key] += values[key]
        return total_values

    def define_resources_dict(self):
        resources = {"vm": {}, "cpu": {}, "memory": {}}
        for field in self.config["resource_definitions"]:
            resources[field]={}
        for key in resources:
            resources[key] = {
                "available": 0,
                "used": 0,
                "free": 0
            }
        return resources

    def add_to_resources(self, resources, resources_type, values):
        for key in values:
            resources[key][resources_type] = values[key]
        return resources

    def update_free_resources(self, resources):
        for key in resources:
            resources[key]["free"] = resources[key]["available"] - resources[key]["used"]
        return resources

    def get_pod_count(self, node = None):
        pods = self.kubernetes.list_all_pods(node)
        return len(pods.items)

    # TODO: This code needs some serious refactoring, create class for resource_dict
    def get(self):
        data = {"nodes":{}}
        nodes = self.kubernetes.list_node()
        available_pcidevices_total = {}
        used_pcidevices_total = {}
        used_resources_total = {}
        available_resources_total = {}
        for node in nodes.items:
            logging.info(f"Getting data for node: {node.metadata.name}")
            resources = self.define_resources_dict()
            pcidevices = self.get_available_pcidevices(node.metadata.name)
            available_pcidevices_total, available_pcidevices = self.count_pcidevices(available_pcidevices_total, pcidevices)
            used_resources, used_pcidevices, pcidevices, vms = self.get_virtualmachine_resources_by_node(node.metadata.name, pcidevices)
            used_pcidevices_total = self.add_totals(used_pcidevices_total, used_pcidevices)
            used_resources_total =  self.add_totals(used_resources_total, used_resources)
            available_resources = self.get_node_resources(node.metadata.name, node.status, ["cpu", "memory"])
            available_resources_total = self.add_totals(available_resources_total, available_resources["allocatable"])
            resources = self.add_to_resources(resources, "available", available_pcidevices)
            resources = self.add_to_resources(resources, "used", used_pcidevices)
            resources = self.add_to_resources(resources, "available", available_resources["allocatable"])
            resources = self.add_to_resources(resources, "used", used_resources)
            resources = self.update_free_resources(resources)
            data["nodes"][node.metadata.name] = {
                "vms": vms,
                "pcidevices": pcidevices,
                "resources": resources
            }
        totals = self.define_resources_dict()
        totals = self.add_to_resources(totals, "available", available_pcidevices_total)
        totals = self.add_to_resources(totals, "available", available_resources_total)
        totals = self.add_to_resources(totals, "used", used_resources_total)
        totals = self.add_to_resources(totals, "used", used_pcidevices_total)
        totals = self.update_free_resources(totals)
        data["totals"] = totals
        return data
