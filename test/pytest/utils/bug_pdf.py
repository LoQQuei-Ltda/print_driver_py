import os
import pytest
from unittest.mock import patch, MagicMock
from src.utils.pdf import PDFUtils

@pytest.fixture
def sample_pdf(tmp_path):
    """Creates a temporary sample PDF file for testing."""
    pdf_path = tmp_path / "sample.pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4\n%Test PDF content\n")
    return str(pdf_path)

def test_get_pdf_info_valid_file(sample_pdf):
    with patch("src.utils.pdf.PdfReader") as mock_pdf_reader:
        # Mock the PdfReader behavior
        mock_reader_instance = MagicMock()
        mock_reader_instance.metadata = {
            "/Title": "Sample PDF",
            "/Author": "Test Author",
        }
        mock_reader_instance.pages = []
        mock_reader_instance.is_encrypted = False
        mock_pdf_reader.return_value = mock_reader_instance

        # Call the method
        pdf_info = PDFUtils.get_pdf_info(sample_pdf)

        # Assertions
        assert pdf_info == {
            "pages": 0,
            "encrypted": False,
            "metadata": {
                "Title": "Sample PDF",
                "Author": "Test Author",
            },
        }
        mock_pdf_reader.assert_called_once_with(sample_pdf)

def test_get_pdf_info_file_not_found():
    with pytest.raises(FileNotFoundError):
        PDFUtils.get_pdf_info("non_existent_file.pdf")