import os
import pytest
from src.config import AppConfig

@pytest.fixture
def mock_data_dir(tmp_path):
    """Fixture to create a temporary mock data directory."""
    data_dir = tmp_path / "data"
    config_dir = data_dir / "config"
    pdf_dir = data_dir / "pdfs"
    config_dir.mkdir(parents=True)
    pdf_dir.mkdir(parents=True)
    return str(data_dir)

def test_app_config_initialization(mock_data_dir):
    # Initialize AppConfig with the mock data directory
    app_config = AppConfig(mock_data_dir)

    # Assertions
    assert app_config.data_dir == mock_data_dir
    assert app_config.config_file == os.path.join(mock_data_dir, "config", "config.json")
    assert app_config.pdf_dir == os.path.join(mock_data_dir, "pdfs")

def test_app_config_directories_exist(mock_data_dir):
    # Ensure the file does not exist before initialization
    config_file_path = os.path.join(mock_data_dir, "config", "config.json")
    assert not os.path.exists(config_file_path)

    # Mock file creation during initialization if necessary
    with patch("builtins.open", create=True):
        # Initialize AppConfig
        app_config = AppConfig(mock_data_dir)

        # Assertions
        assert app_config.pdf_dir == os.path.join(mock_data_dir, "pdfs")
        assert os.path.exists(app_config.pdf_dir) is True