from src.models.printer import Printer

def test_printer_initialization():
    data = {
        "id": "001",
        "name": "Printer A",
        "mac_address": "00:1A:2B:3C:4D:5E"
    }
    printer = Printer(data)
    assert printer.id == "001"
    assert printer.name == "Printer A"
    assert printer.mac_address == "00:1A:2B:3C:4D:5E"

def test_printer_to_dict():
    data = {
        "id": "002",
        "name": "Printer B",
        "mac_address": "11:22:33:44:55:66"
    }
    printer = Printer(data)
    assert printer.to_dict() == data

def test_printer_from_api_response():
    api_response = {
        "id": "003",
        "name": "Printer C",
        "mac_address": "AA:BB:CC:DD:EE:FF"
    }
    printer = Printer.from_api_response(api_response)
    assert printer.id == "003"
    assert printer.name == "Printer C"