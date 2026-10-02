from django.contrib.auth.models import User


def login_new_user(client, username: str = "user", password: str = "test-pass-12345") -> User:
    """Создаёт нового пользователя и логинит его в client (ADR-005: доступ только для вошедших)."""
    user = User.objects.create_user(username=username, password=password)
    client.force_login(user)
    return user
