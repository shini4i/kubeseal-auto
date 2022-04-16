#!/usr/bin/env python

import click
import questionary
from kubernetes import client, config
from icecream import ic

config.load_kube_config()
v1 = client.CoreV1Api()


def find_sealed_secrets_controller():
    for pod in v1.list_pod_for_all_namespaces(watch=False).items:
        if "sealed" in pod.metadata.name:
            click.echo("===> Found the following controller: "
                       f"{pod.metadata.namespace}/{pod.metadata.name}")
            return pod.metadata.namespace


def get_all_namespaces() -> list:
    namespaces = [ns.metadata.name for ns in v1.list_namespace().items]
    ic(namespaces)
    return namespaces


def collect_parameters():
    namespace = questionary.select("Select namespace for the new secret",
                                   choices=get_all_namespaces()).ask()
    secret_type = questionary.select("Select secret type to create",
                                     choices=["generic", "tls", "docker-registry"]).ask()
    secret_name = questionary.text("Provide name for the new secret").ask()

    return {"namespace": namespace, "secret_type": secret_type, "secret_name": secret_name}


def create_generic_secret():
    secrets = []

    click.echo("===> Provide literal entry/entries one per line: "
               "[literal] key=value "
               "[file] filename [end] enter")

    while True:
        secret = questionary.text("Secret Entry").ask()

        if len(secret) > 0:
            secrets.append(secret)
        else:
            break

    ic(secrets)


def main():
    find_sealed_secrets_controller()
    secret_params = collect_parameters()
    ic(secret_params)
    create_generic_secret()


if __name__ == "__main__":
    main()
