# kubeseal-auto

The script is an interactive wrapper for kubeseal binary used to encrypt secrets for [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets).

![demo](assets/demo.gif)

## Installation
pipx can be used to install the script:
```bash
pipx install kubeseal-auto
```

## Usage

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
kubeseal-auto --reencrypt /path/to/directory
```

To back up the encryption keys (not working in a detached mode):
```bash
kubeseal-auto --backup
```
