#!/usr/bin/env python
import subprocess
from tempfile import NamedTemporaryFile

import click
import questionary
import yaml
from icecream import ic
from kubernetes import client, config


class Kubeseal:
    def __init__(self):
        config.load_kube_config()
        context = config.list_kube_config_contexts()[1]["name"]
        click.echo(f"===> Working with [{context}] cluster")

        self.api = client.CoreV1Api()
        self.controller = self.find_sealed_secrets_controller()
        self.temp_file = NamedTemporaryFile()
        click.echo(self.temp_file.name)

    def __del__(self):
        click.echo("===> Removing temporary file")
        self.temp_file.close()

    def find_sealed_secrets_controller(self):
        click.echo("===> Searching for SealedSecrets controller")

        for pod in self.api.list_pod_for_all_namespaces(watch=False).items:
            if "sealed" in pod.metadata.name:
                click.echo(
                    "===> Found the following controller: "
                    f"{pod.metadata.namespace}/{pod.metadata.labels['app.kubernetes.io/instance']}"
                )
                return {
                    "name": pod.metadata.labels["app.kubernetes.io/instance"],
                    "namespace": pod.metadata.namespace,
                }

    def get_all_namespaces(self) -> list:
        namespaces = [ns.metadata.name for ns in self.api.list_namespace().items]
        ic(namespaces)
        return namespaces

    def collect_parameters(self) -> dict:
        namespace = questionary.select(
            "Select namespace for the new secret", choices=self.get_all_namespaces()
        ).ask()
        secret_type = questionary.select(
            "Select secret type to create",
            choices=["generic", "tls", "docker-registry"],
        ).ask()
        secret_name = questionary.text("Provide name for the new secret").ask()

        return {"namespace": namespace, "type": secret_type, "name": secret_name}

    def create_generic_secret(self, secret_params: dict):
        click.echo(
            "===> Provide literal entry/entries one per line: "
            "[literal] key=value "
            "[file] filename"
        )

        secrets = questionary.text("Secret Entries one per line", multiline=True).ask()
        ic(secrets)

        click.echo("===> Generating a temporary generic secret yaml file")

        secret_entries = ""

        for secret in secrets.split():
            if "=" in secret:
                secret_entries = f"{secret_entries} --from-literal={secret}"
            else:
                secret_entries = f"{secret_entries} --from-file={secret}"

        command = (
            f"kubectl create secret generic {secret_params['name']} {secret_entries} "
            f"--namespace {secret_params['namespace']} --dry-run=client -o yaml "
            f"> {self.temp_file.name}"
        )
        ic(command)

        subprocess.call(command, shell=True)

    def seal(self, secret_name: str):
        click.echo("===> Sealing generated secret file")
        command = (
            f"kubeseal --format=yaml "
            f"--controller-namespace={self.controller['namespace']} "
            f"--controller-name={self.controller['name']} < {self.temp_file.name} "
            f"> {secret_name}.yaml"
        )
        ic(command)
        subprocess.call(command, shell=True)

    @staticmethod
    def parse_existing_secret(secret_name: str):
        with open(secret_name, "r") as stream:
            return yaml.safe_load(stream)

    def merge(self, secret_name: str):
        click.echo(f"===> Updating {secret_name}")
        command = (
            f"kubeseal --format=yaml --merge-into {secret_name} "
            f"--controller-namespace={self.controller['namespace']} "
            f"--controller-name={self.controller['name']} < tmp.yaml"
        )
        ic(command)
        subprocess.call(command, shell=True)
        click.echo("===> Done")


@click.command()
@click.option("--debug", required=False, is_flag=True, help="print debug information")
@click.option("--edit", required=False, help="sealed secrets file to edit")
def main(debug, edit):
    if not debug:
        ic.disable()

    kubeseal = Kubeseal()

    if edit:
        secret = kubeseal.parse_existing_secret(edit)
        secret_params = {
            "name": secret["metadata"]["name"],
            "namespace": secret["metadata"]["namespace"],
        }
        ic(secret_params)
        kubeseal.create_generic_secret(secret_params=secret_params)
        kubeseal.merge(edit)
    else:
        secret_params = kubeseal.collect_parameters()
        ic(secret_params)
        kubeseal.create_generic_secret(secret_params=secret_params)
        kubeseal.seal(secret_name=secret_params["name"])


if __name__ == "__main__":
    main()
