from unittest.mock import patch

from click.testing import CliRunner

from kubeseal_auto.cli import cli


def _invoke_cli(args):
    runner = CliRunner()
    return runner.invoke(cli, args)


@patch("kubeseal_auto.cli.Kubeseal")
def test_cli_blocks_fetch_in_detached_mode(mock_kubeseal):
    result = _invoke_cli(["--cert", "cert.crt", "--fetch"])

    assert result.exit_code == 2
    assert "Detached mode (--cert) cannot be combined with --fetch" in result.output
    mock_kubeseal.assert_not_called()


@patch("kubeseal_auto.cli.Kubeseal")
def test_cli_blocks_backup_in_detached_mode(mock_kubeseal):
    result = _invoke_cli(["--cert", "cert.crt", "--backup"])

    assert result.exit_code == 2
    assert "Detached mode (--cert) cannot be combined with --backup" in result.output
    mock_kubeseal.assert_not_called()


@patch("kubeseal_auto.cli.Kubeseal")
def test_cli_blocks_reencrypt_in_detached_mode(mock_kubeseal):
    result = _invoke_cli(["--cert", "cert.crt", "--re-encrypt", "./secrets"])

    assert result.exit_code == 2
    assert "Detached mode (--cert) cannot be combined with --re-encrypt" in result.output
    mock_kubeseal.assert_not_called()


@patch("kubeseal_auto.cli.create_new_secret")
@patch("kubeseal_auto.cli.Kubeseal")
def test_cli_allows_detached_secret_creation(mock_kubeseal, mock_create_new_secret):
    mock_create_new_secret.return_value = None

    result = _invoke_cli(["--cert", "cert.crt"])

    assert result.exit_code == 0
    mock_kubeseal.assert_called_once_with(certificate="cert.crt", select_context=False)
    mock_create_new_secret.assert_called_once_with(kubeseal=mock_kubeseal.return_value)


@patch("kubeseal_auto.cli.Kubeseal")
def test_cli_fetch_without_cert_calls_kubeseal(mock_kubeseal):
    result = _invoke_cli(["--fetch"])

    assert result.exit_code == 0
    mock_kubeseal.assert_called_once_with(select_context=False)
    mock_kubeseal.return_value.fetch_certificate.assert_called_once_with()
