import pytest
from unittest.mock import Mock, patch
from src.installer import VirtualPrinterInstaller

@pytest.fixture
def mock_config():
    """Fixture to provide a mock configuration object."""
    return Mock()

def test_virtual_printer_installer_initialization(mock_config):
    # Initialize the installer
    installer = VirtualPrinterInstaller(mock_config)

    # Assertions
    assert installer.config == mock_config
    assert installer.PRINTER_NAME == "LoQQuei PDF Printer"

@patch("src.installer.subprocess.run")
def test_virtual_printer_installer_install(mock_subprocess_run, mock_config):
    # Mock subprocess.run to simulate successful installation
    mock_subprocess_run.return_value = Mock(returncode=0)

    # Initialize the installer
    installer = VirtualPrinterInstaller(mock_config)

    # Call the install method (assuming it exists)
    installer.install()

    # Assertions
    mock_subprocess_run.assert_called()
    assert mock_subprocess_run.call_args[0][0][0] == "some_install_command"  # Replace with the actual command

@patch("src.installer.subprocess.run")
def test_virtual_printer_installer_install_failure(mock_subprocess_run, mock_config):
    # Mock subprocess.run to simulate a failure
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "some_install_command")

    # Initialize the installer
    installer = VirtualPrinterInstaller(mock_config)

    # Call the install method and ensure it handles the exception
    with pytest.raises(subprocess.CalledProcessError):
        installer.install()

    # Assertions
    mock_subprocess_run.assert_called()