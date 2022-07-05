import os
import platform

import click
import requests
from icecream import ic


class Host:
    def __init__(self):
        self.base_url = (
            "https://github.com/bitnami-labs/sealed-secrets/releases/download"
        )
        self.bin_location = f"{os.path.expanduser('~')}/bin"
        self.cpu_type = self._get_cpu_type()
        self.system = self._get_system_type()

    @staticmethod
    def _get_cpu_type():
        return platform.machine()

    @staticmethod
    def _get_system_type():
        if platform.system() == "Darwin":
            return "darwin"
        elif platform.system() == "Linux":
            return "linux"
        else:
            return "unsupported"

    def _download_kubeseal_binary(self, version: str):
        click.echo("Downloading kubeseal binary")

        url = f"{self.base_url}/v{version}/kubeseal-{version}-{self.system}-{self.cpu_type}.tar.gz"
        ic(url)

        if not os.path.exists(self.bin_location):
            os.makedirs(self.bin_location)

        click.echo(f"Downloading {url}")
        with requests.get(
            f"{self.base_url}/v{version}/kubeseal-{version}-{self.system}-{self.cpu_type}.tar.gz"
        ) as r:
            with open(
                f"/tmp/kubeseal-{version}-{self.system}-{self.cpu_type}.tar.gz", "wb"
            ) as f:
                f.write(r.content)

        os.system(
            f"tar -xvf "
            f"/tmp/kubeseal-{version}-{self.system}-{self.cpu_type}.tar.gz "
            f"-C {self.bin_location} kubeseal"
        )
        os.rename(
            f"{self.bin_location}/kubeseal", f"{self.bin_location}/kubeseal-{version}"
        )
        os.remove(f"/tmp/kubeseal-{version}-{self.system}-{self.cpu_type}.tar.gz")

    def ensure_kubeseal_binary(self, version: str):
        version = version.split("v")[-1]
        if not os.path.exists(f"{self.bin_location}/kubeseal-{version}"):
            click.echo(
                f"kubeseal binary not found at {self.bin_location}/kubeseal-{version}"
            )
            self._download_kubeseal_binary(version)
