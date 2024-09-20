#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = "0.5.0"

import click
import colorama
from icecream import ic

from kubeseal_auto.kubeseal import Kubeseal


def create_new_secret(kubeseal: Kubeseal):
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


def edit_secret(kubeseal: Kubeseal, file: str):
    secret = kubeseal.parse_existing_secret(file)
    secret_params = {
        "name": secret["metadata"]["name"],
        "namespace": secret["metadata"]["namespace"],
    }
    ic(secret_params)
    kubeseal.create_generic_secret(secret_params=secret_params)
    kubeseal.merge(file)


@click.command(help="Automate the process of sealing secrets for Kubernetes")
@click.option("--version", "-v", required=False, is_flag=True, help="print version")
@click.option("--debug", required=False, is_flag=True, help="print debug information")
@click.option("--select", required=False, is_flag=True, default=False, help="prompt for context select")
@click.option("--fetch", required=False, is_flag=True, help="download kubeseal encryption cert")
@click.option("--cert", "-c", required=False, help="certificate to seal secret with")
@click.option("--edit", "-e", required=False, help="SealedSecrets file to edit")
@click.option("--re-encrypt", required=False, help="path to directory with sealed secrets")
@click.option("--backup", required=False, is_flag=True, help="backups controllers encryption secret")
def cli(debug, select, fetch, cert, edit, re_encrypt, backup, version):
    if not debug:
        ic.disable()

    if version:
        click.echo(__version__)
        return

    colorama.init(autoreset=True)

    if cert:
        kubeseal = Kubeseal(certificate=cert, select_context=select)
    else:
        kubeseal = Kubeseal(select_context=select)

    if fetch:
        kubeseal.fetch_certificate()
        return

    if backup:
        kubeseal.backup()
        return

    if re_encrypt:
        kubeseal.reencrypt(src=re_encrypt)
        return

    if edit:
        edit_secret(kubeseal=kubeseal, file=edit)
        return

    create_new_secret(kubeseal=kubeseal)


if __name__ == "__main__":
    cli()
