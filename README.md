<div align="center">

# kubeseal-auto

<b>kubeseal-auto</b> is an interactive wrapper for kubeseal binary used to encrypt secrets for [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets).

![GitHub last commit (branch)](https://img.shields.io/github/last-commit/shini4i/kubeseal-auto/main?style=plastic)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/kubeseal-auto?style=plastic)
![PyPI](https://img.shields.io/pypi/v/kubeseal-auto?style=plastic)
![license](https://img.shields.io/github/license/shini4i/kubeseal-auto?style=plastic)

<img src="https://raw.githubusercontent.com/shini4i/assets/main/src/kubeseal-auto/demo.gif" alt="Showcase" style="max-width: 100%;" width="620">

</div>

## Installation
The recommended way to install this script is [pipx](https://github.com/pypa/pipx):

```bash
pipx install kubeseal-auto
```

## Usage
By default, the script will check the version of sealed-secret controller and download the corresponding kubeseal binary to ~/bin directory.

To run the script in fully interactive mode:
```bash
kubeseal-auto
```

Additionally, a "detached" mode is supported:
```bash
# Download sealed-secrets certificate for local signing
kubeseal-auto --fetch
# Generate SealedSecret with local certificate
kubeseal-auto --cert <kubectl-context>-kubeseal-cert.crt
```
> [!IMPORTANT]
> In the detached mode `kubeseal-auto` will not download the `kubeseal` binary and will look for it in the system $PATH.

To select kubeconfig context:
```bash
kubeseal-auto --select
```

To append or change key values in the existing secret:
```bash
kubeseal-auto --edit secret-name.yaml
```

To reencrypt all secrets in a directory (not working in a detached mode):
```bash
kubeseal-auto --re-encrypt /path/to/directory
```

To back up the encryption and decryption keys (not working in a detached mode):
```bash
kubeseal-auto --backup
```

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
