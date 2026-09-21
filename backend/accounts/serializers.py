from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.utils import get_md5_hash_password
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from datetime import datetime, timezone as datetime_timezone
from .models import CustomUser


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Agrega 'rol' y 'username' al payload del JWT para que el frontend
    pueda distinguir entre médico, recepcionista y administrador sin un fetch extra."""

    remember_me = serializers.BooleanField(default=False, write_only=True)

    def validate(self, attrs):
        identifier = str(attrs.get(self.username_field, '')).strip()
        if '@' in identifier:
            matches = list(get_user_model().objects.filter(email__iexact=identifier, is_active=True).only('username')[:2])
            if len(matches) == 1:
                attrs[self.username_field] = matches[0].username
        data = super().validate(attrs)
        token = RefreshToken(data["refresh"])
        lifetime = settings.REMEMBER_SESSION_LIFETIME if attrs["remember_me"] else settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
        token.set_exp(lifetime=lifetime)
        token["session_expires_at"] = token["exp"]
        token["remember_me"] = attrs["remember_me"]
        return session_pair(token)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["rol"] = user.rol
        token["nombre_completo"] = user.get_full_name()
        return token


def session_pair(token):
    access = token.access_token
    access['exp'] = min(access['exp'], token['session_expires_at'])
    serialized = str(token)
    OutstandingToken.objects.filter(jti=token['jti']).update(token=serialized,
        expires_at=datetime.fromtimestamp(token['exp'], tz=datetime_timezone.utc))
    return {'refresh': serialized, 'access': str(access)}


class SessionTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        old = RefreshToken(attrs['refresh'])
        deadline = old.get('session_expires_at', old['exp'])
        if not isinstance(deadline, int) or deadline <= int(timezone.now().timestamp()):
            raise InvalidToken('La sesión expiró. Inicie sesión nuevamente.')
        try:
            user = get_user_model().objects.get(pk=old[api_settings.USER_ID_CLAIM], is_active=True)
        except get_user_model().DoesNotExist:
            raise AuthenticationFailed('Cuenta no disponible.') from None
        if api_settings.CHECK_REVOKE_TOKEN and old.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
            raise AuthenticationFailed('La contraseña cambió. Inicie sesión nuevamente.')
        # Retain the provider's rotation, active-user validation and blacklist.
        data = super().validate(attrs)
        token = RefreshToken(data['refresh'])
        token['session_expires_at'] = deadline
        token['exp'] = deadline
        token['username'] = user.username
        token['rol'] = user.rol
        token['nombre_completo'] = user.get_full_name()
        return session_pair(token)


class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    def validate_email(self, value):
        if value:
            matches = CustomUser.objects.filter(email__iexact=value)
            if self.instance:
                matches = matches.exclude(pk=self.instance.pk)
            if matches.exists():
                raise serializers.ValidationError('Ese correo ya está asignado a otro usuario.')
        return value

    def validate(self, attrs):
        from django.contrib.auth.password_validation import validate_password
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Se requiere una contraseña."})
        if attrs.get("password"):
            from django.core.exceptions import ValidationError
            try:
                validate_password(attrs["password"], user=self.instance)
            except ValidationError as exc:
                raise serializers.ValidationError({"password": exc.messages})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return CustomUser.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance

    class Meta:
        model = CustomUser
        fields = ("id", "username", "email", "first_name", "last_name", "rol", "is_active", "date_joined", "last_login", "password")
        read_only_fields = ("id", "date_joined", "last_login")
