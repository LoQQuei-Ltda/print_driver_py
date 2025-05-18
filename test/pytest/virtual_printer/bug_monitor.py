import pytest
from unittest.mock import Mock, patch, call
from src.monitor import PrintFolderMonitor # type: ignore

@pytest.fixture
def mock_config(tmp_path):
    """Fixture to provide a mock configuration object."""
    config = Mock()
    config.print_folder = str(tmp_path / "print_folder")
    return config

@pytest.fixture
def mock_api_client():
    """Fixture to provide a mock API client."""
    return Mock()

def test_print_folder_monitor_initialization(mock_config, mock_api_client):
    # Mock callback
    mock_callback = Mock()

    # Initialize the monitor
    monitor = PrintFolderMonitor(mock_config, mock_api_client, mock_callback)

    # Assertions
    assert monitor.config == mock_config
    assert monitor.api_client == mock_api_client
    assert monitor.on_new_document == mock_callback

@patch("src.monitor.os.path.exists", return_value=True)
@patch("src.monitor.os.listdir", return_value=["doc1.pdf", "doc2.pdf"])
def test_print_folder_monitor_scan(mock_listdir, mock_path_exists, mock_config, mock_api_client):
    # Mock callback
    mock_callback = Mock()

    # Initialize the monitor
    monitor = PrintFolderMonitor(mock_config, mock_api_client, mock_callback)

    # Call the scan method (assuming it exists)
    monitor.scan_folder()

    # Assertions
    mock_path_exists.assert_called_once_with(mock_config.print_folder)
    mock_listdir.assert_called_once_with(mock_config.print_folder)
    assert mock_callback.call_count == 2  # Called for each document

@patch("src.monitor.os.path.exists", return_value=False)
def test_print_folder_monitor_scan_folder_not_found(mock_path_exists, mock_config, mock_api_client):
    # Mock callback
    mock_callback = Mock()

    # Initialize the monitor
    monitor = PrintFolderMonitor(mock_config, mock_api_client, mock_callback)

    # Call the scan method and ensure it handles the missing folder gracefully
    monitor.scan_folder()

    # Assertions
    mock_path_exists.assert_called_once_with(mock_config.print_folder)
    assert mock_callback.call_count == 0  # No documents processed