from src.models.user import User

def test_user_initialization():
    data = {
        "id": "001",
        "email": "user@example.com",
        "name": "John Doe",
        "token": "abc123",
        "created_at": "2023-01-01T12:00:00",
        "last_login": "2023-01-02T12:00:00",
        "preferences": {"theme": "dark"}
    }
    user = User(data)
    assert user.id == "001"
    assert user.email == "user@example.com"
    assert user.name == "John Doe"
    assert user.token == "abc123"
    assert user.created_at == "2023-01-01T12:00:00"
    assert user.last_login == "2023-01-02T12:00:00"
    assert user.preferences == {"theme": "dark"}

def test_user_to_dict():
    data = {
        "id": "002",
        "email": "anotheruser@example.com",
        "name": "Jane Doe",
        "token": "xyz789",
        "created_at": "2023-02-01T12:00:00",
        "last_login": "2023-02-02T12:00:00",
        "preferences": {"language": "en"}
    }
    user = User(data)
    assert user.to_dict() == data