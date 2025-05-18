import pytest
from unittest.mock import patch, MagicMock
from src.utils.printer_utils import PrinterUtils

def test_get_system_printers_windows():
    # Mock the platform.system() to return "Windows"
    with patch("src.utils.printer_utils.platform.system", return_value="Windows"):
        # Mock the subprocess.check_output to simulate printer list output
        with patch("src.utils.printer_utils.subprocess.check_output") as mock_check_output:
            mock_check_output.return_value = b"Printer1\nPrinter2\nPrinter3\n"

            # Call the method
            printers = PrinterUtils.get_system_printers()

            # Assertions
            assert printers == [
                {"name": "Printer1"},
                {"name": "Printer2"},
                {"name": "Printer3"},
            ]
            mock_check_output.assert_called_once()

def test_get_system_printers_non_windows():
    # Mock the platform.system() to return "Linux"
    with patch("src.utils.printer_utils.platform.system", return_value="Linux"):
        # Mock the subprocess.check_output to simulate printer list output
        with patch("src.utils.printer_utils.subprocess.check_output") as mock_check_output:
            mock_check_output.return_value = b"PrinterA\nPrinterB\n"

            # Call the method
            printers = PrinterUtils.get_system_printers()

            # Assertions
            assert printers == [
                {"name": "PrinterA"},
                {"name": "PrinterB"},
            ]
            mock_check_output.assert_called_once()