import pytest
from unittest.mock import Mock
from src.tasks import update_printers_task
from src.models.printer import Printer

def test_update_printers_task_success():
    # Mock the API client
    mock_api_client = Mock()
    mock_api_client.get_printers.return_value = [
        {"id": "001", "name": "Printer A", "mac_address": "00:1A:2B:3C:4D:5E"},
        {"id": "002", "name": "Printer B", "mac_address": "11:22:33:44:55:66"},
    ]

    # Mock the config
    mock_config = Mock()

    # Call the task
    update_printers_task(mock_api_client, mock_config)

    # Assertions
    mock_api_client.get_printers.assert_called_once()
    # Add more assertions if the task modifies `mock_config` or performs other actions

def test_update_printers_task_api_failure():
    # Mock the API client to raise an exception
    mock_api_client = Mock()
    mock_api_client.get_printers.side_effect = Exception("API error")

    # Mock the config
    mock_config = Mock()

    # Call the task and ensure it handles the exception
    try:
        update_printers_task(mock_api_client, mock_config)
    except Exception:
        pytest.fail("update_printers_task raised an exception unexpectedly")

    # Assertions
    mock_api_client.get_printers.assert_called_once()