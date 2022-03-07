# kubeseal-auto

The script is an interactive wrapper for kubeseal binary used to encrypt secrets for [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets).

[![asciicast](https://asciinema.org/a/fc0wjij4cijESNjHyf0gElhE0.svg)](https://asciinema.org/a/fc0wjij4cijESNjHyf0gElhE0)

## Installation
Homebrew can be used to install the script with all dependencies:
```bash
brew tap shini4i/tap
brew install kubeseal-auto
```

## Usage

To run the script in fully interactive mode:
```bash
kubeseal-auto
```

To append or change key values in existing secret:
```bash
kubeseal-auto -e secret-name.yaml
```

NOTE: The script is using active kubectl context. Providing a different context is not supported yes.

Additionally, a limited "detached" mode is supported:
```bash
# Download sealed-secrets certificate for local signing
kubeseal-auto --fetch
# Generate SealedSecret with local certificate
kubeseal-auto --cert <kubectl-context>-cert.crt
```
