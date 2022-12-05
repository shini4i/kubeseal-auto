import click
import questionary
from colorama import Fore
from icecream import ic
from kubernetes import client, config

from kubeseal_auto.host import Host


class Cluster:
    def __init__(self, select_context: bool):
        self.context = self._set_context(select_context=select_context)
        config.load_kube_config(context=self.context)
        self.host = Host()
        self.controller = self._find_sealed_secrets_controller()

    @staticmethod
    def _set_context(select_context: bool):
        contexts, current_context = config.list_kube_config_contexts()
        if select_context:
            contexts = [context["name"] for context in contexts]
            context = questionary.select("Select context to work with", choices=contexts).ask()
        else:
            context = current_context["name"]
        click.echo(f"===> Working with [{Fore.CYAN}{context}{Fore.RESET}] cluster")
        return context

    @staticmethod
    def get_all_namespaces() -> list:
        ns_list = []

        for ns in client.CoreV1Api().list_namespace().items:
            ns_list.append(ns.metadata.name)
        ic(ns_list)

        return ns_list

    @staticmethod
    def _find_sealed_secrets_controller() -> dict:
        click.echo("===> Searching for SealedSecrets controller")

        expected_label = "app.kubernetes.io/instance"

        for deployment in client.AppsV1Api().list_deployment_for_all_namespaces(label_selector=expected_label).items:
            if "sealed-secrets" in deployment.metadata.labels[expected_label]:
                name = deployment.metadata.labels[expected_label]
                namespace = deployment.metadata.namespace
                version = deployment.metadata.labels[
                    "app.kubernetes.io/version"
                ]

                click.echo(
                    "===> Found the following controller: "
                    f"[{Fore.CYAN}{namespace}/{name}{Fore.RESET}]\n"
                    "===> Controller version: "
                    f"[{Fore.CYAN}{version}{Fore.RESET}]"
                )

                return {
                    "name": name,
                    "namespace": namespace,
                    "version": version,
                }

        click.echo("===> No controller found")
        exit(1)

    def find_latest_sealed_secrets_controller_certificate(self) -> str:
        res = client.CoreV1Api().list_namespaced_secret(self.controller.get("namespace"))
        secrets = []
        for secret in res.items:
            if "sealed-secrets" in secret.metadata.name and secret.type == "kubernetes.io/tls":
                secrets.append({"name": secret.metadata.name, "timestamp": secret.metadata.creation_timestamp})

        ic(secrets)

        if secrets:
            secrets.sort(key=lambda x: x["timestamp"])

        return secrets[-1]["name"]

    def ensure_kubeseal_version(self, version: str):
        self.host.ensure_kubeseal_binary(version=version)

    def get_controller_name(self):
        return self.controller["name"]

    def get_controller_namespace(self):
        return self.controller["namespace"]

    def get_controller_version(self):
        return self.controller["version"].split("v")[-1]

    def get_context(self):
        return self.context
