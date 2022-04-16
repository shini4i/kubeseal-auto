#!/usr/bin/env python

import click
import inquirer
from kubernetes import client, config

config.load_kube_config()
v1 = client.CoreV1Api()


def find_sealed_secrets_controller():
    for pod in v1.list_pod_for_all_namespaces(watch=False).items:
        if "sealed" in pod.metadata.name:
            click.echo("===> Found the following controller: "
                       f"{pod.metadata.namespace}/{pod.metadata.name}")
            return pod.metadata.namespace


def get_all_namespaces():
    namespaces = [ns.metadata.name for ns in v1.list_namespace().items]
    click.echo(f"===> Found the following namespaces: {namespaces}")
    return namespaces


def collect_parameters():
    parameters = [
        inquirer.List('namespace',
                      message="Select namespace for the new secret",
                      choices=get_all_namespaces(),
                      ),
        inquirer.List('secret_type',
                      message="Select secret type to create",
                      choices=["generic", "tls", "docker-registry"]),
        inquirer.Text('secret_name',
                      message="Provide name for the new secret")
    ]

    return inquirer.prompt(parameters)


def main():
    find_sealed_secrets_controller()
    secret_params = collect_parameters()
    click.echo(secret_params)


if __name__ == "__main__":
    main()
