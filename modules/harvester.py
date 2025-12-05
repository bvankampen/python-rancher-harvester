from .kubernetes import Kubernetes
from .rancher import Rancher
from .utils import merge_dict, b64decode
from .templates import Template

import yaml


class Harvester:
    def __init__(self, config, blueprint):
        self.config = merge_dict(config, blueprint)
        self.rancher = Rancher(config)
        self.kubernetes = Kubernetes(
            self.rancher.get_kubeconfig(self.config["harvester"]["cluster_name"])
        )

    def find_pcidevice_by_address(self, address):
        for device in self.all_node_pcidevices["items"]:
            if "address" in device["status"]:
                if device["status"]["address"] == address:
                    return {
                        "name": device["metadata"]["name"],
                        "deviceName": device["status"]["resourceName"],
                    }
        return None

    def get_pcidevices(self, harvester_node, wanted_pcidevices):
        pcidevices = []
        self.all_node_pcidevices = self.kubernetes.list(
            "devices.harvesterhci.io",
            "v1beta1",
            "pcidevices",
            f"nodename={harvester_node}",
        )
        for wanted_pcidevice in wanted_pcidevices:
            if wanted_pcidevice in self.config["machines"]["pcidevices"]:
                if "address" in self.config["machines"]["pcidevices"][wanted_pcidevice]:
                    for address in self.config["machines"]["pcidevices"][
                        wanted_pcidevice
                    ]["address"]:
                        pcidevice = self.find_pcidevice_by_address(address)
                        if pcidevice is not None:
                            pcidevices.append(pcidevice)
        return pcidevices

    def get_os_disk(self, vm, image_name):
        image = self.kubernetes.list(
            "harvesterhci.io",
            "v1beta1",
            "virtualmachineimages",
            f"harvesterhci.io/imageDisplayName={image_name}",
        )
        return {
            "metadata": {
                "name": f"{vm['name']}-disk-0",
                "annotations": {
                    "harvesterhci.io/imageId": f"{image['items'][0]['metadata']['namespace']}/{image['items'][0]['metadata']['name']}"
                },
            },
            "spec": {
                "accessModes": ["ReadWriteMany"],
                "resources": {"requests": {"storage": f"{vm['disk_size']}Gi"}},
                "volumeMode": "Block",
                "storageClassName": f"{image['items'][0]['status']['storageClassName']}",
            },
        }

    def get_extra_disk(self, vm, disk, count):
        return {
            "metadata": {
                "name": f"{vm['name']}-disk-{count}",
            },
            "spec": {
                "accessModes": ["ReadWriteMany"],
                "resources": {"requests": {"storage": f"{disk['disk_size']}Gi"}},
                "volumeMode": "Block",
                "storageClassName": f"{disk['storageclass']}",
            },
        }

    def create_csi_cloudconfig(self, blueprint):
        service_account_name = self.config["cluster"]["name"]
        cluster_name = self.config["cluster"]["name"]
        namespace = self.config["machines"]["namespace"]
        self.kubernetes.create_namespace(namespace)
        self.kubernetes.create_service_account(namespace, service_account_name)
        self.kubernetes.create_namespaced_cluster_role_binding(
            namespace=namespace,
            name=f"{namespace}-{service_account_name}",
            cluster_role_name="harvesterhci.io:cloudprovider",
            service_account_name=service_account_name,
        )
        service_account = self.kubernetes.get_service_account(
            namespace=namespace, service_account_name=service_account_name
        )

        service_account_token_name = f"{service_account_name}-token"

        self.kubernetes.create_service_account_token(
            namespace=namespace,
            name=service_account_token_name,
            service_account_name=service_account_name,
            service_account_uid=service_account.metadata.uid,
        )

        service_account_token = self.kubernetes.get_secret(
            namespace=namespace, secret_name=service_account_token_name
        )

        vip_config_map = self.kubernetes.get_config_map("harvester-system", "vip")

        token = b64decode(service_account_token.data["token"])

        kubeconfig = self.kubernetes.create_kubeconfig(
            namespace=namespace,
            cluster=cluster_name,
            context=f"{service_account_name}-{namespace}-{cluster_name}",
            user=f"{service_account_name}-{namespace}-{cluster_name}",
            token=token,
            endpoint=f"https://{vip_config_map.data['ip']}:6443",
            ca_cert=service_account_token.data["ca.crt"],
        )

        return yaml.dump(kubeconfig)

    def create_vms(self, blueprint, dry_run=False):
        if self.config["kubernetes"]["rke2_provisioned_install"]:
            node_command = self.rancher.get_rke2_node_command(
                self.config["cluster"]["name"]
            )
        else:
            node_command = ""

        if self.config["kubernetes"]["install_harvester_csi"]:
            csi_cloudconfig = self.create_csi_cloudconfig(blueprint)

        for vm in blueprint["machines"]["vms"]:
            disks = []
            pcidevices = []
            if "pcidevices" in vm:
                pcidevices = self.get_pcidevices(vm["harvester_node"], vm["pcidevices"])
            image_name = self.config["machines"]["template_image_name"]
            if "type" in vm:
                if vm["type"] == "gpu":
                    image_name = self.config["machines"]["template_image_name_gpu"]

            disks.append(self.get_os_disk(vm, image_name))
            if "extra_disks" in vm:
                count = 1
                for disk in vm["extra_disks"]:
                    disks.append(self.get_extra_disk(vm, disk, count))
                    count += 1

            template = Template("virtualmachine")
            vm_manifest = template.parse(
                blueprint=self.config,
                vm=vm,
                pcidevices=pcidevices,
                disks=disks,
            )

            role = ""
            for r in vm["role"]:
                role = f"{role} --{r}".strip()

            template = Template("user-data")
            cloudinit_user_data = template.parse(
                blueprint=self.config,
                vm=vm,
                csi_cloudconfig=csi_cloudconfig,
                node_command=node_command,
                role=role,
            )

            template = Template("network-data")
            cloudinit_network_data = template.parse(
                blueprint=self.config,
                vm=vm,
            )

            template = Template("cloudinit-secret")
            cloudinit_secret = template.parse(
                blueprint=self.config,
                vm=vm,
                cloudinit_user_data=cloudinit_user_data,
                cloudinit_network_data=cloudinit_network_data,
            )

            if dry_run:
                print(f"--- {vm['name']}")
                print(yaml.dump(cloudinit_secret))
                print(yaml.dump(vm_manifest))
                print("---")
            else:
                self.kubernetes.create(
                    cloudinit_secret, blueprint["machines"]["namespace"]
                )
                self.kubernetes.create(vm_manifest, blueprint["machines"]["namespace"])
