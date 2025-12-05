from .templates import Template
from .api import Api
from .kubernetes import Kubernetes
from .utils import merge_dict
from time import sleep

import yaml


class Rancher:
    def __init__(self, config):
        self.config = config
        self.api = Api(self.config["rancher"]["hostname"], self.config["api_token"])

    def get_cluster_id(self, cluster_name):
        data = self.api.get(f"/v3/clusters?name={cluster_name}")
        return data["data"][0]["id"]

    def get_kubeconfig(self, cluster_name):
        cluster_id = self.get_cluster_id(cluster_name)
        data = self.api.post(f"/v3/clusters/{cluster_id}?action=generateKubeconfig")
        if "config" in data:
            return yaml.safe_load(data["config"])
        else:
            return {}

    def get_rke2_node_command(self, cluster_name):
        cluster_id = self.get_cluster_id(cluster_name)
        data = self.api.get(f"/v3/clusters/{cluster_id}/clusterregistrationtokens")
        return data["data"][0]["nodeCommand"]

    def get_cluster(self, cluster_name):
        kubeconfig = self.get_kubeconfig(self.config["rancher"]["cluster_name"])
        kubernetes = Kubernetes(kubeconfig)
        return kubernetes.get(
            group="provisioning.cattle.io",
            version="v1",
            plural="clusters",
            name=cluster_name,
            namespace="fleet-default",
        )

    def wait_for_cluster(self, blueprint):
        while True:
            cluster = self.get_cluster(blueprint["cluster"]["name"])
            if cluster is not None:
                for condition in cluster["status"]["conditions"]:
                    if condition["type"] == "Ready":
                        # print(
                        #     f"Cluster {blueprint['cluster']['name']} Ready state: {condition['reason']}"
                        # )
                        if condition["reason"] == "Waiting":
                            return
            # else:
            #     print(f"Cluster {blueprint['cluster']['name']} not found")
            sleep(1)

    def create_cluster(self, blueprint, dry_run=False):
        kubeconfig = self.get_kubeconfig(self.config["rancher"]["cluster_name"])
        template = Template("cluster")
        cluster_manifest = template.parse(blueprint=merge_dict(self.config, blueprint))
        kubernetes = Kubernetes(kubeconfig)
        if dry_run:
            print(yaml.dump(cluster_manifest))
            print("---")
            return None
        else:
            return kubernetes.create(cluster_manifest, "fleet-default")
