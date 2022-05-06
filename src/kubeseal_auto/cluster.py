import click
from colorama import Fore
from icecream import ic
from kubernetes import client, config


class Cluster:
    def __init__(self):
        config.load_kube_config()
        self.context = config.list_kube_config_contexts()[1]["name"]
        self.controller = self.find_sealed_secrets_controller()

    @staticmethod
    def get_all_namespaces() -> list:
        namespaces = [
            ns.metadata.name for ns in client.CoreV1Api().list_namespace().items
        ]
        ic(namespaces)
        return namespaces

    @staticmethod
    def find_sealed_secrets_controller() -> dict:
        click.echo("===> Searching for SealedSecrets controller")

        for deployment in client.AppsV1Api().list_deployment_for_all_namespaces().items:
            if "sealed" in deployment.metadata.name:
                name = deployment.metadata.labels["app.kubernetes.io/instance"]
                namespace = deployment.metadata.namespace
                click.echo(
                    "===> Found the following controller: "
                    f"{Fore.CYAN}{namespace}/{name}"
                )
                return {
                    "name": name,
                    "namespace": namespace,
                }

    def get_controller_name(self):
        return self.controller["name"]

    def get_controller_namespace(self):
        return self.controller["namespace"]

    def get_context(self):
        return self.context
