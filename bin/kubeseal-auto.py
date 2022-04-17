#!/usr/bin/env python

import subprocess

import click
import questionary
from icecream import ic
from kubernetes import client
from kubernetes import config

config.load_kube_config()
v1 = client.CoreV1Api()
controller = {}


def find_sealed_secrets_controller():
    global controller

    for pod in v1.list_pod_for_all_namespaces(watch=False).items:
        if "sealed" in pod.metadata.name:
            click.echo(
                "===> Found the following controller: "
                f"{pod.metadata.namespace}/{pod.metadata.labels['app.kubernetes.io/instance']}"
            )
            controller = {
                "name": pod.metadata.labels["app.kubernetes.io/instance"],
                "namespace": pod.metadata.namespace,
            }
            return


def get_all_namespaces() -> list:
    namespaces = [ns.metadata.name for ns in v1.list_namespace().items]
    ic(namespaces)
    return namespaces


def collect_parameters() -> dict:
    namespace = questionary.select(
        "Select namespace for the new secret", choices=get_all_namespaces()
    ).ask()
    secret_type = questionary.select(
        "Select secret type to create", choices=["generic", "tls", "docker-registry"]
    ).ask()
    secret_name = questionary.text("Provide name for the new secret").ask()

    return {"namespace": namespace, "type": secret_type, "name": secret_name}


def create_generic_secret(secret_params: dict):
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
        f"--namespace {secret_params['namespace']} --dry-run=client -o yaml > tmp.yaml"
    )
    ic(command)

    subprocess.call(command, shell=True)


def seal(secret_name: str):
    click.echo("===> Sealing generated secret file")
    command = (
        f"kubeseal --format=yaml "
        f"--controller-namespace={controller['namespace']} "
        f"--controller-name={controller['name']} < tmp.yaml > {secret_name}.yaml"
    )
    ic(command)
    subprocess.call(command, shell=True)


@click.command()
@click.option("--debug", required=False, is_flag=True, help="print debug information")
def main(debug):
    if not debug:
        ic.disable()

    find_sealed_secrets_controller()
    secret_params = collect_parameters()
    ic(secret_params)
    create_generic_secret(secret_params=secret_params)
    seal(secret_name=secret_params["name"])


if __name__ == "__main__":
    main()
