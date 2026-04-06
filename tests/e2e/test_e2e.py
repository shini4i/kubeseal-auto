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


@pytest.mark.e2e
def test_01_fetch_certificate(
    e2e_workdir: Path,
    kind_context: str,
    spawn_env: dict[str, str],
) -> None:
    """Fetch the kubeseal encryption certificate from the cluster."""
    child = pexpect.spawn(
        "kubeseal-auto",
        ["--fetch"],
        cwd=str(e2e_workdir),
        env=spawn_env,
        timeout=60,
    )
    child.expect(pexpect.EOF)
    child.close()

    assert child.exitstatus == 0, f"kubeseal-auto --fetch failed:\n{child.before}"

    cert_file = e2e_workdir / f"{kind_context}-kubeseal-cert.crt"
    assert cert_file.exists(), "Certificate file was not created"
    assert cert_file.stat().st_size > 0, "Certificate file is empty"


@pytest.mark.e2e
def test_02_create_seal_connected(
    e2e_workdir: Path,
    spawn_env: dict[str, str],
) -> None:
    """Create and seal a generic secret in connected mode."""
    child = pexpect.spawn(
        "kubeseal-auto",
        [],
        cwd=str(e2e_workdir),
        env=spawn_env,
        timeout=60,
    )

    # 1. Namespace prompt (autocomplete) — type "default" and press Enter
    child.expect("namespace", timeout=30)
    child.sendline("default")

    # 2. Secret type (select) — "generic" is first, press Enter
    child.expect("[Ss]ecret type", timeout=10)
    child.sendline("")

    # 3. Secret name (text)
    child.expect("name", timeout=10)
    child.sendline("e2e-test-secret")

    # 4. Entry type (select) — "Literal" is first, press Enter
    child.expect("[Aa]dd secret entry", timeout=10)
    child.sendline("")

    # 5. Key=value (text)
    child.expect("key=value", timeout=10)
    child.sendline("username=admin")

    # 6. Entry type again — navigate to "Done" (4th option, 3 downs)
    child.expect("[Aa]dd secret entry", timeout=10)
    child.send(_DOWN)
    child.send(_DOWN)
    child.send(_DOWN)
    child.sendline("")

    child.expect(pexpect.EOF, timeout=60)
    child.close()

    assert child.exitstatus == 0, f"Connected seal failed:\n{child.before}"

    sealed_file = e2e_workdir / "e2e-test-secret.yaml"
    assert sealed_file.exists(), "Sealed secret file was not created"

    content = yaml.safe_load(sealed_file.read_text())
    assert content["kind"] == "SealedSecret"
    assert content["metadata"]["name"] == "e2e-test-secret"
    assert content["metadata"]["namespace"] == "default"
    assert "username" in content["spec"]["encryptedData"]


@pytest.mark.e2e
def test_03_create_seal_detached(
    e2e_workdir: Path,
    kind_context: str,
    spawn_env: dict[str, str],
) -> None:
    """Create and seal a generic secret in detached mode using a certificate."""
    cert_path = e2e_workdir / f"{kind_context}-kubeseal-cert.crt"
    assert cert_path.exists(), "Certificate from test_01 not found — tests must run in order"

    child = pexpect.spawn(
        "kubeseal-auto",
        ["--cert", str(cert_path)],
        cwd=str(e2e_workdir),
        env=spawn_env,
        timeout=60,
    )

    # 1. Namespace prompt (text input in detached mode)
    child.expect("namespace", timeout=30)
    child.sendline("default")

    # 2. Secret type — "generic" is first
    child.expect("[Ss]ecret type", timeout=10)
    child.sendline("")

    # 3. Secret name
    child.expect("name", timeout=10)
    child.sendline("e2e-detached-secret")

    # 4. Entry type — "Literal" is first
    child.expect("[Aa]dd secret entry", timeout=10)
    child.sendline("")

    # 5. Key=value
    child.expect("key=value", timeout=10)
    child.sendline("token=abc123")

    # 6. Done (3 downs)
    child.expect("[Aa]dd secret entry", timeout=10)
    child.send(_DOWN)
    child.send(_DOWN)
    child.send(_DOWN)
    child.sendline("")

    child.expect(pexpect.EOF, timeout=60)
    child.close()

    assert child.exitstatus == 0, f"Detached seal failed:\n{child.before}"

    sealed_file = e2e_workdir / "e2e-detached-secret.yaml"
    assert sealed_file.exists(), "Detached sealed secret file was not created"

    content = yaml.safe_load(sealed_file.read_text())
    assert content["kind"] == "SealedSecret"
    assert content["metadata"]["name"] == "e2e-detached-secret"
    assert "token" in content["spec"]["encryptedData"]


@pytest.mark.e2e
def test_04_edit_secret(
    e2e_workdir: Path,
    spawn_env: dict[str, str],
) -> None:
    """Edit an existing sealed secret by merging a new entry."""
    sealed_file = e2e_workdir / "e2e-test-secret.yaml"
    assert sealed_file.exists(), "Sealed secret from test_02 not found — tests must run in order"

    child = pexpect.spawn(
        "kubeseal-auto",
        ["--edit", str(sealed_file)],
        cwd=str(e2e_workdir),
        env=spawn_env,
        timeout=60,
    )

    # Edit flow only prompts for entries (name/namespace come from the file)
    # 1. Entry type — "Literal" is first
    child.expect("[Aa]dd secret entry", timeout=30)
    child.sendline("")

    # 2. Key=value
    child.expect("key=value", timeout=10)
    child.sendline("password=secret123")

    # 3. Done (3 downs)
    child.expect("[Aa]dd secret entry", timeout=10)
    child.send(_DOWN)
    child.send(_DOWN)
    child.send(_DOWN)
    child.sendline("")

    child.expect(pexpect.EOF, timeout=60)
    child.close()

    assert child.exitstatus == 0, f"Edit failed:\n{child.before}"

    content = yaml.safe_load(sealed_file.read_text())
    assert content["kind"] == "SealedSecret"
    assert "username" in content["spec"]["encryptedData"]
    assert "password" in content["spec"]["encryptedData"]


@pytest.mark.e2e
def test_05_reencrypt(
    e2e_workdir: Path,
    spawn_env: dict[str, str],
) -> None:
    """Re-encrypt all sealed secrets in the working directory."""
    # Collect sealed secret files before re-encryption for comparison
    sealed_files = list(e2e_workdir.glob("*.yaml"))
    assert sealed_files, "No sealed secret files found — earlier tests must run first"

    original_data = {}
    for f in sealed_files:
        content = yaml.safe_load(f.read_text())
        if content and content.get("kind") == "SealedSecret":
            original_data[f.name] = content["spec"]["encryptedData"].copy()

    assert original_data, "No valid SealedSecret files found in workdir"

    child = pexpect.spawn(
        "kubeseal-auto",
        ["--re-encrypt", str(e2e_workdir)],
        cwd=str(e2e_workdir),
        env=spawn_env,
        timeout=120,
    )
    child.expect(pexpect.EOF)
    child.close()

    assert child.exitstatus == 0, f"Re-encrypt failed:\n{child.before}"

    # Verify files are still valid SealedSecrets with the same keys
    for filename, old_encrypted in original_data.items():
        filepath = e2e_workdir / filename
        assert filepath.exists(), f"{filename} disappeared after re-encryption"

        content = yaml.safe_load(filepath.read_text())
        assert content["kind"] == "SealedSecret"
        assert set(content["spec"]["encryptedData"].keys()) == set(old_encrypted.keys())
