from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailOrUsernameBackend(ModelBackend):
    """
    Custom authentication backend that allows users to authenticate
    using either their email address or their username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('email')
            
        if not username or not password:
            return None

        try:
            # Look up by case-insensitive email or case-insensitive username
            user = User.objects.filter(
                Q(email__iexact=username) | Q(username__iexact=username)
            ).first()

            if user and user.check_password(password) and self.user_can_authenticate(user):
                return user
        except Exception:
            return None

        return None
