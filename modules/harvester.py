from .kubernetes import Kubernetes
from .rancher import Rancher
from .utils import merge_dict, b64decode
from .templates import Template
from .resources import Resources

import yaml
from ipaddress import IPv4Network

import logging

logger = logging.getLogger(__name__)


class Harvester:
    def __init__(self, config, blueprint):
        self.config = merge_dict(config, blueprint)
        self.rancher = Rancher(config)
        self.kubernetes = Kubernetes(
            self.rancher.get_kubeconfig(self.config["harvester"]["cluster_name"])
        )
        self.resources = Resources(self.config, self.kubernetes)

    def find_pcidevice_by_address(self, all_node_pcidevices, address):
        for device in all_node_pcidevices["items"]:
            if "address" in device["status"]:
                if device["status"]["address"] == address:
                    return {
                        "name": device["metadata"]["name"],
                        "deviceName": device["status"]["resourceName"],
                    }
        return None

    def get_pcidevices(self, harvester_node, wanted_pcidevices):
        pcidevices = []
        all_node_pcidevices = self.kubernetes.list_cluster(
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
                        pcidevice = self.find_pcidevice_by_address(all_node_pcidevices, address)
                        if pcidevice is not None:
                            pcidevices.append(pcidevice)
        return pcidevices



    def get_os_disk(self, vm, image_name):
        image = self.kubernetes.list_cluster(
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

    def create_csi_cloudconfig(self):
        service_account_name = self.config["cluster"]["name"]
        cluster_name = self.config["cluster"]["name"]
        namespace = self.config["machines"]["namespace"]

        logging.info(f"Create CSI Cloudconfig for {cluster_name}")

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

    def create_vms(self, updatevm=False, updatevm_names=""):
        if updatevm_names != "":
            updatevm_names = updatevm_names.split(",")
        else:
            updatevm_names = []

        node_command = ""
        csi_cloudconfig = ""

        if "rke2_provisioned_install" in self.config["kubernetes"]:
            if self.config["kubernetes"]["rke2_provisioned_install"]:
                node_command = self.rancher.get_rke2_node_command(
                    self.config["cluster"]["name"]
                )
            if self.config["kubernetes"]["install_harvester_csi"]:
                csi_cloudconfig = self.create_csi_cloudconfig()

        for vm in self.config["machines"]["vms"]:
            logger.info(f"Create VM {vm['name']}")
            disks = []
            pcidevices = []
            if "pcidevices" in vm:
            # TODO: Move this code to the resources module, to enable caching
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
            if "role" in vm:
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

            if "cluster" not in self.config:
                # create namespace if vm only provisioning
                self.kubernetes.create_namespace(self.config["machines"]["namespace"])

            vminfo = self.kubernetes.get(
                "kubevirt.io",
                "v1",
                "virtualmachines",
                vm["name"],
                namespace=self.config["machines"]["namespace"],
            )

            if (
                vminfo is None
                or (updatevm and vm["name"] in updatevm_names)
                or (updatevm and updatevm_names == [])
            ):
                logging.warning(f"Updating {vm['name']}")
                result = self.kubernetes.create(
                    cloudinit_secret, self.config["machines"]["namespace"]
                )
                if result:
                    print(result)
                result = self.kubernetes.create(
                    vm_manifest, self.config["machines"]["namespace"]
                )
                if result:
                    print(result)
            else:
                logger.warning(f"VM {vm['name']} already exists")

    def get_resources(self):
        return self.resources.get()

    def create_vm_network(self):
        if "vlan_id" not in self.config["network"]:
            logger.warning("No vlan_id configured, vlan won't be provisioned")
            return
        namespace = self.config["network"]["name"].split("/")[0]
        name = self.config["network"]["name"].split("/")[1]
        network = self.kubernetes.get(
            "k8s.cni.cncf.io",
            "v1",
            "network-attachment-definitions",
            name,
            namespace=namespace)
        cidr = str(IPv4Network(
            f"{self.config['network']['gateway']}/{self.config['network']['netmask']}", False))
        if network is None:
            template = Template("network-attachment-definition")
            network_attachment_definition_manifest = template.parse(
                blueprint = self.config,
                name = name,
                namespace = namespace,
                cidr = cidr
            )
            logger.info(f"Create network {name} in namespace {namespace}")
            result = self.kubernetes.create(network_attachment_definition_manifest, namespace)
            if result:
                print(result)
        else:
            logger.warning(f"Network {name} in namespace {namespace} already exists")

    def create_ip_pool(self):
        if "ip_pool" not in self.config["network"]:
            logger.warning(f"No IP Pool configured")
            return
        name = f"{self.config['cluster']['name']}-ip-pool"
        cidr = str(IPv4Network(
            f"{self.config['network']['gateway']}/{self.config['network']['netmask']}", False))
        ip_pool = self.kubernetes.get(
            "loadbalancer.harvesterhci.io",
            "v1beta1",
            "ippools",
            name)
        if ip_pool is None:
            template = Template("ip-pool")
            ip_pool_manifest = template.parse(
                blueprint = self.config,
                name = name,
                cidr = cidr
            )
            logger.info(f"Create IP Pool {name}")
            result = self.kubernetes.create(ip_pool_manifest)
            if result:
                print(result)
        else:
            logger.warning(f"IP Pool {name} already exists")

    def provision(self, args):
        self.create_vm_network()
        self.create_ip_pool()
        self.create_vms(args.updatevm, args.vms)
