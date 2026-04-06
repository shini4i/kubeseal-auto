"""End-to-end tests for kubeseal-auto.

These tests exercise the real CLI against a kind cluster with the
sealed-secrets controller installed. They are ordered sequentially
(by numeric prefix) because later tests depend on artifacts produced
by earlier ones.

Requires: a reachable Kubernetes cluster with sealed-secrets controller.
Skipped automatically when no cluster is available (see conftest.py).
"""

from pathlib import Path

import pexpect
import pytest
import yaml

# Arrow-key escape sequence for navigating questionary select menus
_DOWN = "\x1b[B"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spawn(
    args: list[str],
    *,
    cwd: str,
    env: dict[str, str],
    timeout: int = 60,
) -> pexpect.spawn:
    """Spawn a kubeseal-auto process with common defaults."""
    return pexpect.spawn(
        "kubeseal-auto",
        args,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )


def _finish(child: pexpect.spawn, *, label: str, timeout: int = 60) -> None:
    """Wait for EOF and assert exit code 0."""
    child.expect(pexpect.EOF, timeout=timeout)
    child.close()
    assert child.exitstatus == 0, f"{label} failed:\n{child.before}"


def _select_down(child: pexpect.spawn, n: int) -> None:
    """Send *n* down-arrow keys then Enter to confirm the selection."""
    for _ in range(n):
        child.send(_DOWN)
    child.sendline("")


def _fill_secret_params(
    child: pexpect.spawn,
    *,
    namespace: str,
    secret_type_downs: int,
    name: str,
) -> None:
    """Answer the namespace / secret-type / name prompts."""
    child.expect("namespace", timeout=30)
    child.sendline(namespace)

    child.expect("[Ss]ecret type", timeout=10)
    _select_down(child, secret_type_downs)

    child.expect("name", timeout=10)
    child.sendline(name)


def _add_literal_then_done(child: pexpect.spawn, literal: str) -> None:
    """Add a single literal entry then select Done."""
    # "Literal" is the first option
    child.expect("[Aa]dd secret entry", timeout=10)
    child.sendline("")

    child.expect("key=value", timeout=10)
    child.sendline(literal)

    # "Done" is the 4th option (3 downs)
    child.expect("[Aa]dd secret entry", timeout=10)
    _select_down(child, 3)


def _assert_sealed_secret(
    path: Path,
    *,
    name: str,
    expected_keys: list[str] | None = None,
) -> None:
    """Load a YAML file and assert it is a valid SealedSecret."""
    assert path.exists(), f"Sealed secret file {path.name} was not created"
    content = yaml.safe_load(path.read_text())
    assert content["kind"] == "SealedSecret"
    assert content["metadata"]["name"] == name
    if expected_keys:
        for key in expected_keys:
            assert key in content["spec"]["encryptedData"], f"Key '{key}' missing from encryptedData"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_01_fetch_certificate(
    e2e_workdir: Path,
    kind_context: str,
    spawn_env: dict[str, str],
) -> None:
    """Fetch the kubeseal encryption certificate from the cluster."""
    child = _spawn(["--fetch"], cwd=str(e2e_workdir), env=spawn_env)
    _finish(child, label="kubeseal-auto --fetch")

    cert_file = e2e_workdir / f"{kind_context}-kubeseal-cert.crt"
    assert cert_file.exists(), "Certificate file was not created"
    assert cert_file.stat().st_size > 0, "Certificate file is empty"


@pytest.mark.e2e
def test_02_create_generic_connected(
    e2e_workdir: Path,
    spawn_env: dict[str, str],
) -> None:
    """Create and seal a generic secret in connected mode."""
    child = _spawn([], cwd=str(e2e_workdir), env=spawn_env)

    _fill_secret_params(child, namespace="default", secret_type_downs=0, name="e2e-test-secret")
    _add_literal_then_done(child, "username=admin")

    _finish(child, label="Connected generic seal")

    _assert_sealed_secret(
        e2e_workdir / "e2e-test-secret.yaml",
        name="e2e-test-secret",
        expected_keys=["username"],
    )


@pytest.mark.e2e
def test_03_create_generic_detached(
    e2e_workdir: Path,
    kind_context: str,
    spawn_env: dict[str, str],
    kubeseal_on_path: None,
) -> None:
    """Create and seal a generic secret in detached mode using a certificate."""
    cert_path = e2e_workdir / f"{kind_context}-kubeseal-cert.crt"
    assert cert_path.exists(), "Certificate from test_01 not found — tests must run in order"

    child = _spawn(["--cert", str(cert_path)], cwd=str(e2e_workdir), env=spawn_env)

    _fill_secret_params(child, namespace="default", secret_type_downs=0, name="e2e-detached-secret")
    _add_literal_then_done(child, "token=abc123")

    _finish(child, label="Detached generic seal")

    _assert_sealed_secret(
        e2e_workdir / "e2e-detached-secret.yaml",
        name="e2e-detached-secret",
        expected_keys=["token"],
    )


@pytest.mark.e2e
def test_04_create_tls_connected(
    e2e_workdir: Path,
    spawn_env: dict[str, str],
) -> None:
    """Create and seal a TLS secret in connected mode."""
    # TLS creation expects tls.key and tls.crt in the working directory
    key_file = e2e_workdir / "tls.key"
    cert_file = e2e_workdir / "tls.crt"

    # Generate a self-signed certificate for testing
    import subprocess

    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key_file),
            "-out",
            str(cert_file),
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=e2e-test",
        ],
        check=True,
        capture_output=True,
    )

    child = _spawn([], cwd=str(e2e_workdir), env=spawn_env)

    # TLS is the 2nd option (1 down)
    _fill_secret_params(child, namespace="default", secret_type_downs=1, name="e2e-tls-secret")
    # No entry prompts for TLS — it reads tls.key and tls.crt automatically

    _finish(child, label="Connected TLS seal")

    _assert_sealed_secret(
        e2e_workdir / "e2e-tls-secret.yaml",
        name="e2e-tls-secret",
        expected_keys=["tls.crt", "tls.key"],
    )


@pytest.mark.e2e
def test_05_create_regcred_connected(
    e2e_workdir: Path,
    spawn_env: dict[str, str],
) -> None:
    """Create and seal a docker-registry secret in connected mode."""
    child = _spawn([], cwd=str(e2e_workdir), env=spawn_env)

    # docker-registry is the 3rd option (2 downs)
    _fill_secret_params(child, namespace="default", secret_type_downs=2, name="e2e-regcred-secret")

    # Docker credentials prompts
    child.expect("docker-server", timeout=10)
    child.sendline("ghcr.io")

    child.expect("docker-username", timeout=10)
    child.sendline("testuser")

    child.expect("docker-password", timeout=10)
    child.sendline("testpass")

    _finish(child, label="Connected docker-registry seal")

    _assert_sealed_secret(
        e2e_workdir / "e2e-regcred-secret.yaml",
        name="e2e-regcred-secret",
        expected_keys=[".dockerconfigjson"],
    )


@pytest.mark.e2e
def test_06_edit_secret(
    e2e_workdir: Path,
    spawn_env: dict[str, str],
) -> None:
    """Edit an existing sealed secret by merging a new entry."""
    sealed_file = e2e_workdir / "e2e-test-secret.yaml"
    assert sealed_file.exists(), "Sealed secret from test_02 not found — tests must run in order"

    child = _spawn(["--edit", str(sealed_file)], cwd=str(e2e_workdir), env=spawn_env)

    # Edit flow only prompts for entries (name/namespace come from the file)
    _add_literal_then_done(child, "password=secret123")

    _finish(child, label="Edit secret")

    _assert_sealed_secret(
        sealed_file,
        name="e2e-test-secret",
        expected_keys=["username", "password"],
    )


@pytest.mark.e2e
def test_07_backup(
    e2e_workdir: Path,
    kind_context: str,
    spawn_env: dict[str, str],
) -> None:
    """Backup the controller's encryption secret."""
    child = _spawn(["--backup"], cwd=str(e2e_workdir), env=spawn_env)
    _finish(child, label="kubeseal-auto --backup")

    backup_file = e2e_workdir / f"{kind_context}-secret-backup.yaml"
    assert backup_file.exists(), "Backup file was not created"

    content = yaml.safe_load(backup_file.read_text())
    assert content["kind"] == "Secret"
    assert content["type"] == "kubernetes.io/tls"


@pytest.mark.e2e
def test_08_reencrypt(
    e2e_workdir: Path,
    spawn_env: dict[str, str],
) -> None:
    """Re-encrypt all sealed secrets in the working directory."""
    sealed_files = list(e2e_workdir.glob("*.yaml"))
    assert sealed_files, "No sealed secret files found — earlier tests must run first"

    original_data = {}
    for f in sealed_files:
        content = yaml.safe_load(f.read_text())
        if content and content.get("kind") == "SealedSecret":
            original_data[f.name] = content["spec"]["encryptedData"].copy()

    assert original_data, "No valid SealedSecret files found in workdir"

    child = _spawn(["--re-encrypt", str(e2e_workdir)], cwd=str(e2e_workdir), env=spawn_env, timeout=120)
    _finish(child, label="Re-encrypt", timeout=120)

    # Verify files are still valid SealedSecrets with the same keys
    for filename, old_encrypted in original_data.items():
        filepath = e2e_workdir / filename
        assert filepath.exists(), f"{filename} disappeared after re-encryption"

        content = yaml.safe_load(filepath.read_text())
        assert content["kind"] == "SealedSecret"
        assert set(content["spec"]["encryptedData"].keys()) == set(old_encrypted.keys())
