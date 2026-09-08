from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """Reemplaza el endpoint /api/token/ para incluir 'rol' en el JWT."""
    serializer_class = CustomTokenObtainPairSerializer
