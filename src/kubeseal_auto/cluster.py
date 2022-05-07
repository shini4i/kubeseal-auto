import click
import questionary
from colorama import Fore
from icecream import ic
from kubernetes import client, config


class Cluster:
    def __init__(self):
        self.context = self._select_context()
        config.load_kube_config(context=self.context)
        self.controller = self._find_sealed_secrets_controller()

    @staticmethod
    def _select_context():
        contexts, _ = config.list_kube_config_contexts()
        contexts = [context["name"] for context in contexts]
        return questionary.select("Select context to work with", choices=contexts).ask()

    @staticmethod
    def get_all_namespaces() -> list:
        ns_list = [ns.metadata.name for ns in client.CoreV1Api().list_namespace().items]
        ic(ns_list)
        return ns_list

    @staticmethod
    def _find_sealed_secrets_controller() -> dict:
        click.echo("===> Searching for SealedSecrets controller")

        # Here we are basically making an educated guess that deployment that contains
        # "sealed" in name is the one we are looking for.
        # It will be good to change this logic to something more reasonable in the future.
        for deployment in client.AppsV1Api().list_deployment_for_all_namespaces().items:
            if "sealed" in deployment.metadata.name:
                name = deployment.metadata.labels["app.kubernetes.io/instance"]
                namespace = deployment.metadata.namespace
                click.echo(
                    f"===> Found the following controller: {Fore.CYAN}{namespace}/{name}"
                )
                return {"name": name, "namespace": namespace}

    def get_controller_name(self):
        return self.controller["name"]

    def get_controller_namespace(self):
        return self.controller["namespace"]

    def get_context(self):
        return self.context
