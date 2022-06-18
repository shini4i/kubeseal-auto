#!/usr/bin/env python
# -*- coding: utf-8 -*-

import click
import colorama
from icecream import ic

from kubeseal_auto.kubeseal import Kubeseal


@click.command()
@click.option("--debug", required=False, is_flag=True, help="print debug information")
@click.option(
    "--select",
    required=False,
    is_flag=True,
    default=False,
    help="prompt for context select",
)
@click.option(
    "--fetch", required=False, is_flag=True, help="download kubeseal encryption cert"
)
@click.option("--cert", required=False, help="certificate to seal secret with")
@click.option("--edit", required=False, help="SealedSecrets file to edit")
@click.option(
    "--reencrypt", required=False, help="path to directory with sealed secrets"
)
@click.option(
    "--backup",
    required=False,
    is_flag=True,
    help="backups controllers encryption secret",
)
def cli(debug, select, fetch, cert, edit, reencrypt, backup):
    if not debug:
        ic.disable()

    colorama.init(autoreset=True)

    if cert:
        kubeseal = Kubeseal(certificate=cert, select_context=select)
    else:
        kubeseal = Kubeseal(select_context=select)

    if fetch:
        kubeseal.fetch_certificate()
    elif backup:
        kubeseal.backup()
    elif reencrypt:
        kubeseal.reencrypt(src=reencrypt)
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
    cli()
