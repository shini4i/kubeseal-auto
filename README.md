# kubeseal-auto

The script is an interactive wrapper for kubeseal binary used to encrypt secrets for [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets).

[![asciicast](https://asciinema.org/a/ynpQetDq5gPnKgNhAo5oYH6hK.svg)](https://asciinema.org/a/ynpQetDq5gPnKgNhAo5oYH6hK)

## Installation
Homebrew can be used to install the script with all dependencies:
```bash
pip install kubeseal-auto
```

## Usage

To run the script in fully interactive mode:
```bash
kubeseal-auto
```

To append or change key values in existing secret:
```bash
kubeseal-auto --edit secret-name.yaml
```
Additionally, a "detached" mode is supported:
```bash
# Download sealed-secrets certificate for local signing
kubeseal-auto --fetch
# Generate SealedSecret with local certificate
kubeseal-auto --cert <kubectl-context>-kubeseal-cert.crt
```
NOTE: The script is using active kubectl context. Providing a different context is not supported yet.
