from kubernetes import client, config, utils
from kubernetes.client.rest import ApiException
from .utils import print_api_error

import yaml


class Kubernetes:
    def __init__(self, kubeconfig):
        configuration = client.Configuration()
        config.load_kube_config_from_dict(
            kubeconfig, client_configuration=configuration
        )
        self.api_client = client.ApiClient(configuration=configuration)

    def create(self, manifest, namespace):
        if not isinstance(manifest, dict):
            manifest = yaml.safe_load(manifest)
        try:
            utils.create_from_dict(
                k8s_client=self.api_client,
                data=manifest,
                verbose=False,
                namespace=namespace,
                apply=True,
            )
        except utils.FailToCreateError as e:
            return str(e)
        return None

    def list(self, group, version, plural, label_selector="", namespace=None):
        api = client.CustomObjectsApi(self.api_client)
        if namespace is None:
            return api.list_cluster_custom_object(
                group=group,
                version=version,
                plural=plural,
                label_selector=label_selector,
            )
        else:
            return api.list_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                label_selector=label_selector,
            )

    def get(self, group, version, plural, name, label_selector="", namespace=None):
        api = client.CustomObjectsApi(self.api_client)
        if namespace is None:
            try:
                return api.get_cluster_custom_object(
                    group=group,
                    version=version,
                    plural=plural,
                    name=name,
                    label_selector=label_selector,
                )
            except ApiException:
                return None
        else:
            try:
                return api.get_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural,
                    name=name,
                )
            except ApiException:
                return None

    def create_namespace(self, namespace):
        api = client.CoreV1Api(self.api_client)
        try:
            api.create_namespace(
                body=client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
            )
        except ApiException as e:
            print_api_error(e)

    def create_service_account(self, namespace, name):
        api = client.CoreV1Api(self.api_client)
        try:
            api.create_namespaced_service_account(
                namespace=namespace,
                body=client.V1ServiceAccount(metadata=client.V1ObjectMeta(name=name)),
            )
        except ApiException as e:
            print_api_error(e)

    def create_namespaced_cluster_role_binding(
        self, namespace, name, cluster_role_name, service_account_name
    ):
        api = client.RbacAuthorizationV1Api(self.api_client)
        try:
            api.create_namespaced_role_binding(
                namespace=namespace,
                body=client.V1RoleBinding(
                    metadata=client.V1ObjectMeta(name=name),
                    role_ref=client.V1RoleRef(
                        api_group="rbac.authorization.k8s.io",
                        kind="ClusterRole",
                        name=cluster_role_name,
                    ),
                    subjects=[
                        client.RbacV1Subject(
                            kind="ServiceAccount",
                            name=service_account_name,
                            namespace=namespace,
                        )
                    ],
                ),
            )
        except ApiException as e:
            print_api_error(e)

    def get_service_account(self, namespace, service_account_name):
        api = client.CoreV1Api(self.api_client)
        return api.read_namespaced_service_account(
            namespace=namespace, name=service_account_name
        )

    def create_service_account_token(
        self, namespace, name, service_account_name, service_account_uid
    ):
        api = client.CoreV1Api(self.api_client)
        try:
            api.create_namespaced_secret(
                namespace=namespace,
                body=client.V1Secret(
                    metadata=client.V1ObjectMeta(
                        name=name,
                        namespace=namespace,
                        annotations={
                            "kubernetes.io/service-account.name": service_account_name,
                            "kubernetes.io/service-account.uid": service_account_uid,
                        },
                        owner_references=[
                            client.V1OwnerReference(
                                api_version="v1",
                                kind="ServiceAccount",
                                name=service_account_name,
                                uid=service_account_uid,
                            )
                        ],
                    ),
                    type="kubernetes.io/service-account-token",
                ),
            )
        except ApiException as e:
            print_api_error(e)

    def get_secret(self, namespace, secret_name):
        api = client.CoreV1Api(self.api_client)
        return api.read_namespaced_secret(namespace=namespace, name=secret_name)

    def get_config_map(self, namespace, config_map_name):
        api = client.CoreV1Api(self.api_client)
        return api.read_namespaced_config_map(namespace=namespace, name=config_map_name)

    def create_kubeconfig(
        self, namespace, cluster, context, user, token, endpoint, ca_cert
    ):
        return {
            "apiVersion": "v1",
            "clusters": [
                {
                    "cluster": {
                        "certificate-authority-data": ca_cert,
                        "server": endpoint,
                    },
                    "name": cluster,
                }
            ],
            "contexts": [
                {
                    "context": {
                        "cluster": cluster,
                        "namespace": namespace,
                        "user": user,
                    },
                    "name": context,
                }
            ],
            "current-context": context,
            "kind": "Config",
            "preferences": {},
            "users": [{"name": user, "user": {"token": token}}],
        }
