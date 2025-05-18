import os
import pytest
from src.models.document import Document

def test_document_initialization():
    data = {
        "id": "123",
        "name": "test_document.txt",
        "path": "/path/to/test_document.txt",
        "size": 1024,
        "created_at": "2023-01-01T12:00:00"
    }
    doc = Document(data)
    assert doc.id == "123"
    assert doc.name == "test_document.txt"
    assert doc.path == "/path/to/test_document.txt"
    assert doc.size == 1024
    assert doc.created_at == "2023-01-01T12:00:00"

def test_document_to_dict():
    data = {
        "id": "123",
        "name": "test_document.txt",
        "path": "/path/to/test_document.txt",
        "size": 1024,
        "created_at": "2023-01-01T12:00:00"
    }
    doc = Document(data)
    assert doc.to_dict() == data

def test_document_from_api_response():
    api_response = {
        "id": "456",
        "name": "api_document.txt",
        "path": "/path/to/api_document.txt",
        "size": 2048,
        "created_at": "2023-02-01T12:00:00"
    }
    doc = Document.from_api_response(api_response)
    assert doc.id == "456"
    assert doc.name == "api_document.txt"
    assert doc.path == "/path/to/api_document.txt"
    assert doc.size == 2048
    assert doc.created_at == "2023-02-01T12:00:00"

def test_document_from_file(tmp_path):
    file_path = tmp_path / "file_document.txt"
    file_path.write_text("Sample content")
    doc = Document.from_file(str(file_path))
    assert doc.name == "file_document.txt"
    assert doc.path == str(file_path)
    assert doc.size == len("Sample content")
    assert doc.file_exists is True

def test_document_file_exists(tmp_path):
    file_path = tmp_path / "existing_file.txt"
    file_path.write_text("Content")
    doc = Document({"path": str(file_path)})
    assert doc.file_exists is True

    non_existing_doc = Document({"path": "/non/existing/path.txt"})
    assert non_existing_doc.file_exists is False

def test_document_formatted_size():
    doc = Document({"size": 512})
    assert doc.formatted_size == "512 B"

    doc = Document({"size": 2048})
    assert doc.formatted_size == "2.0 KB"

    doc = Document({"size": 1048576})
    assert doc.formatted_size == "1.0 MB"

    doc = Document({"size": 1073741824})
    assert doc.formatted_size == "1.0 GB"

def test_document_formatted_date():
    doc = Document({"created_at": "2023-01-01T12:00:00"})
    assert doc.formatted_date == "01/01/2023 12:00"

    invalid_doc = Document({"created_at": "invalid_date"})
    assert invalid_doc.formatted_date == "invalid_date"

def test_document_str():
    doc = Document({"id": "789", "name": "string_document.txt", "size": 1024})
    assert str(doc) == "Document(id=789, name=string_document.txt, size=1.0 KB)"