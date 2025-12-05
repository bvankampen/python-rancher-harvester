import requests
import logging

requests.packages.urllib3.disable_warnings()
logger = logging.getLogger(__name__)


class Api:
    def __init__(self, rancher_host, token, tls_verify=False):
        self.rancher_host = rancher_host
        self.tls_verify = tls_verify
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def get(self, path):
        url = f"https://{self.rancher_host}/{path}"
        result = requests.get(url=url, headers=self.headers, verify=self.tls_verify)
        return result.json()

    def post(self, path, data=None):
        url = f"https://{self.rancher_host}/{path}"
        result = requests.post(
            url=url, data=data, headers=self.headers, verify=self.tls_verify
        )
        return result.json()
