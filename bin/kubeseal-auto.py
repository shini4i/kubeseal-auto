#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
from tempfile import NamedTemporaryFile

import click
import colorama
import questionary
import yaml
from colorama import Fore
from icecream import ic
from kubernetes import client, config


class Kubeseal:
    def __init__(self, certificate=None):
        self.detached_mode = False
        if certificate is not None:
            click.echo("Working in a detached mode")
            self.detached_mode = True
            self.certificate = certificate
        else:
            config.load_kube_config()
            self.context = config.list_kube_config_contexts()[1]["name"]
            click.echo(
                f"===> Working with [{Fore.CYAN}{self.context}{Fore.RESET}] cluster"
            )
            self.api = client.CoreV1Api()
            self.controller = self.find_sealed_secrets_controller()
        self.temp_file = NamedTemporaryFile()

    def __del__(self):
        click.echo("===> Removing temporary file")
        self.temp_file.close()

    def find_sealed_secrets_controller(self):
        click.echo("===> Searching for SealedSecrets controller")

        for pod in self.api.list_pod_for_all_namespaces(watch=False).items:
            if "sealed" in pod.metadata.name:
                name = pod.metadata.labels["app.kubernetes.io/instance"]
                namespace = pod.metadata.namespace
                click.echo(
                    "===> Found the following controller: "
                    f"{Fore.CYAN}{namespace}/{name}"
                )
                return {
                    "name": name,
                    "namespace": namespace,
                }

    def get_all_namespaces(self) -> list:
        namespaces = [ns.metadata.name for ns in self.api.list_namespace().items]
        ic(namespaces)
        return namespaces

    def collect_parameters(self) -> dict:
        if self.detached_mode:
            namespace = questionary.text(
                "Provide namespace for the new secret"
            ).unsafe_ask()
        else:
            namespace = questionary.select(
                "Select namespace for the new secret", choices=self.get_all_namespaces()
            ).unsafe_ask()
        secret_type = questionary.select(
            "Select secret type to create",
            choices=["generic", "tls", "docker-registry"],
        ).unsafe_ask()
        secret_name = questionary.text("Provide name for the new secret").unsafe_ask()

        return {"namespace": namespace, "type": secret_type, "name": secret_name}

    def create_generic_secret(self, secret_params: dict):
        click.echo(
            "===> Provide literal entry/entries one per line: "
            f"[{Fore.CYAN}literal{Fore.RESET}] key=value "
            f"[{Fore.CYAN}file{Fore.RESET}] filename"
        )

        secrets = questionary.text(
            "Secret Entries one per line", multiline=True
        ).unsafe_ask()
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

    def create_tls_secret(self, secret_params: dict):
        click.echo("===> Generating a temporary tls secret yaml file")
        command = (
            f"kubectl create secret tls {secret_params['name']} "
            f"--namespace {secret_params['namespace']} --key tls.key --cert tls.crt "
            f"--dry-run=client -o yaml > {self.temp_file.name}"
        )
        ic(command)

        subprocess.call(command, shell=True)

    def create_regcred_secret(self, secret_params: dict):
        click.echo("===> Generating a temporary tls secret yaml file")

        docker_server = questionary.text("Provide docker-server").unsafe_ask()
        docker_username = questionary.text("Provide docker-username").unsafe_ask()
        docker_password = questionary.text("Provide docker-password").unsafe_ask()

        command = (
            f"kubectl create secret docker-registry {secret_params['name']} "
            f"--namespace {secret_params['namespace']} "
            f"--docker-server={docker_server} "
            f"--docker-username={docker_username} "
            f"--docker-password={docker_password} "
            f"--dry-run=client -o yaml > {self.temp_file.name}"
        )
        ic(command)

        subprocess.call(command, shell=True)

    def seal(self, secret_name: str):
        click.echo("===> Sealing generated secret file")
        if self.detached_mode:
            command = (
                f"kubeseal --format=yaml "
                f"--cert={self.certificate} < {self.temp_file.name} "
                f"> {secret_name}.yaml"
            )
        else:
            command = (
                f"kubeseal --format=yaml "
                f"--controller-namespace={self.controller['namespace']} "
                f"--controller-name={self.controller['name']} < {self.temp_file.name} "
                f"> {secret_name}.yaml"
            )
        ic(command)
        subprocess.call(command, shell=True)
        click.echo("===> Done")

    @staticmethod
    def parse_existing_secret(secret_name: str):
        with open(secret_name, "r") as stream:
            return yaml.safe_load(stream)

    def merge(self, secret_name: str):
        click.echo(f"===> Updating {secret_name}")
        if self.detached_mode:
            command = (
                f"kubeseal --format=yaml --merge-into {secret_name} "
                f"--cert={self.certificate} < {self.temp_file.name} "
            )
        else:
            command = (
                f"kubeseal --format=yaml --merge-into {secret_name} "
                f"--controller-namespace={self.controller['namespace']} "
                f"--controller-name={self.controller['name']} < {self.temp_file.name}"
            )
        ic(command)
        subprocess.call(command, shell=True)
        click.echo("===> Done")

    def fetch_certificate(self):
        click.echo("===> Downloading certificate for kubeseal...")
        command = (
            f"kubeseal --controller-namespace {self.controller['namespace']} "
            f"--controller-name {self.controller['name']} --fetch-cert "
            f"> {self.context}-kubeseal-cert.crt"
        )
        ic(command)
        subprocess.call(command, shell=True)
        click.echo(f"===> Saved to {Fore.CYAN}{self.context}-kubeseal-cert.crt")


@click.command()
@click.option("--debug", required=False, is_flag=True, help="print debug information")
@click.option(
    "--fetch", required=False, is_flag=True, help="download kubeseal encryption cert"
)
@click.option("--cert", required=False, help="certificate to seal secret with")
@click.option("--edit", required=False, help="SealedSecrets file to edit")
def main(debug, fetch, cert, edit):
    if not debug:
        ic.disable()

    colorama.init(autoreset=True)

    if cert:
        kubeseal = Kubeseal(certificate=cert)
    else:
        kubeseal = Kubeseal()

    if fetch:
        kubeseal.fetch_certificate()
    elif edit:
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

        match secret_params["type"]:
            case "generic":
                kubeseal.create_generic_secret(secret_params=secret_params)
            case "tls":
                kubeseal.create_tls_secret(secret_params=secret_params)
            case "docker-registry":
                kubeseal.create_regcred_secret(secret_params=secret_params)

        kubeseal.seal(secret_name=secret_params["name"])


if __name__ == "__main__":
    main()
