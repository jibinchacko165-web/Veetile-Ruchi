from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom Authentication Backend for Veetile-Ruchi:
    Authenticates users cleanly against:
    1. Username (case-insensitive)
    2. Email (case-insensitive)
    
    Uses Django's built-in check_password() without modifying user records or password hashes.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        clean_identifier = username.strip()

        try:
            # 1. Match by username (case-insensitive)
            user = User.objects.filter(username__iexact=clean_identifier).first()
            if user and user.check_password(password) and self.user_can_authenticate(user):
                return user

            # 2. Match by email (case-insensitive)
            user = User.objects.filter(email__iexact=clean_identifier).first()
            if user and user.check_password(password) and self.user_can_authenticate(user):
                return user

        except Exception:
            return None

        return None

    def get_user(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
            return user if self.user_can_authenticate(user) else None
        except User.DoesNotExist:
            return None


