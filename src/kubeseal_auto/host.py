import os
import platform

import click
import requests
from icecream import ic


class Host:
    def __init__(self):
        self.base_url = "https://github.com/bitnami-labs/sealed-secrets/releases/download"
        self.bin_location = f"{os.path.expanduser('~')}/bin"
        self.cpu_type = self._get_cpu_type()
        self.system = self._get_system_type()

    @staticmethod
    def _get_cpu_type():
        match platform.machine():
            case "x86_64":
                return "amd64"
            case "arm64":
                return "arm64"
            case _:
                click.echo(f"Unsupported CPU: {platform.machine()}")
                exit(1)

    @staticmethod
    def _get_system_type():
        match platform.system():
            case "Linux":
                return "linux"
            case "Darwin":
                return "darwin"
            case _:
                click.echo(f"Unsupported system: {platform.system()}")
                exit(1)

    def _download_kubeseal_binary(self, version: str):
        click.echo("Downloading kubeseal binary")

        url = f"{self.base_url}/v{version}/kubeseal-{version}-{self.system}-{self.cpu_type}.tar.gz"
        ic(url)
        local_path = f"/tmp/kubeseal-{version}-{self.system}-{self.cpu_type}.tar.gz"
        ic(local_path)

        if not os.path.exists(self.bin_location):
            os.makedirs(self.bin_location)

        click.echo(f"Downloading {url}")
        with requests.get(url) as r:
            if r.status_code == 404:
                click.echo(f"The required version {version} is not available")
                raise FileNotFoundError
            with open(local_path, "wb") as f:
                f.write(r.content)

        os.system(f"tar -xvf {local_path} -C {self.bin_location} kubeseal")
        os.rename(f"{self.bin_location}/kubeseal", f"{self.bin_location}/kubeseal-{version}")
        os.remove(local_path)

    def ensure_kubeseal_binary(self, version: str):
        version = version.split("v")[-1]
        if not os.path.exists(f"{self.bin_location}/kubeseal-{version}"):
            click.echo(
                f"kubeseal binary not found at {self.bin_location}/kubeseal-{version}"
            )
            self._download_kubeseal_binary(version)
