import subprocess
from tempfile import NamedTemporaryFile

import click
import questionary
import yaml
from colorama import Fore
from icecream import ic

from kubeseal_auto.cluster import Cluster


class Kubeseal:
    def __init__(self, select_context: bool, certificate=None):
        self.detached_mode = False

        if certificate is not None:
            click.echo("===> Working in a detached mode")
            self.detached_mode = True
            self.certificate = certificate
        else:
            cluster = Cluster(select_context=select_context)
            self.controller_name = cluster.get_controller_name()
            self.controller_namespace = cluster.get_controller_namespace()
            self.current_context_name = cluster.get_context()
            self.namespaces_list = cluster.get_all_namespaces()

        self.temp_file = NamedTemporaryFile()

    def __del__(self):
        click.echo("===> Removing temporary file")
        self.temp_file.close()

    def collect_parameters(self) -> dict:
        if self.detached_mode:
            namespace = questionary.text(
                "Provide namespace for the new secret"
            ).unsafe_ask()
        else:
            namespace = questionary.select(
                "Select namespace for the new secret",
                choices=self.namespaces_list,
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
                f"--context={self.current_context_name} "
                f"--controller-namespace={self.controller_namespace} "
                f"--controller-name={self.controller_name} < {self.temp_file.name} "
                f"> {secret_name}.yaml"
            )
        ic(command)
        subprocess.call(command, shell=True)
        self.append_argo_annotation(filename=f"{secret_name}.yaml")
        click.echo("===> Done")

    @staticmethod
    def parse_existing_secret(secret_name: str):
        try:
            with open(secret_name, "r") as stream:
                try:
                    return yaml.safe_load(stream)
                except yaml.YAMLError:
                    click.echo("Provided file is an invalid yaml. Aborting.")
                    exit(1)
        except FileNotFoundError:
            click.echo("Provided file does not exists. Aborting.")
            exit(1)

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
                f"--context={self.current_context_name} "
                f"--controller-namespace={self.controller_namespace} "
                f"--controller-name={self.controller_name} < {self.temp_file.name}"
            )
        ic(command)
        subprocess.call(command, shell=True)
        self.append_argo_annotation(filename=secret_name)
        click.echo("===> Done")

    def append_argo_annotation(self, filename: str):
        """
        This method is used to append an annotations that will allow
        ArgoCD to process git repository which has SealedSecrets before
        the related controller is deployed in the cluster

        Parameters:
             filename: the filename of the resulting yaml file
        """
        secret = self.parse_existing_secret(filename)

        click.echo("===> Appending ArgoCD related annotations")
        secret["metadata"]["annotations"] = {
            "argocd.argoproj.io/sync-options": "SkipDryRunOnMissingResource=true"
        }

        with open(filename, "w") as file:
            yaml.dump(secret, file)

    def fetch_certificate(self):
        """
        This method downloads a certificate that can be used in the future
        to encrypt secrets without direct access to the cluster
        """
        click.echo("===> Downloading certificate for kubeseal...")
        command = (
            f"kubeseal --controller-namespace {self.controller_namespace} "
            f"--context={self.current_context_name} "
            f"--controller-name {self.controller_name} --fetch-cert "
            f"> {self.current_context_name}-kubeseal-cert.crt"
        )
        ic(command)
        subprocess.call(command, shell=True)
        click.echo(
            f"===> Saved to {Fore.CYAN}{self.current_context_name}-kubeseal-cert.crt"
        )
