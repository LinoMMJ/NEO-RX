from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CustomUser


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Agrega 'rol' y 'username' al payload del JWT para que el frontend
    pueda distinguir entre médico, técnico y administrador sin un fetch extra."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["rol"] = user.rol
        token["nombre_completo"] = user.get_full_name()
        return token


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ("id", "username", "email", "first_name", "last_name", "rol")
        read_only_fields = ("id",)
