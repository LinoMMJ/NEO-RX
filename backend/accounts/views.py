"""
Views de autenticación con rate limiting.

Endpoints:
- POST /api/token/           → Login (rate limited: 5/min por IP)
- POST /api/token/refresh/   → Refresh token (rate limited: 20/min por IP)
- POST /api/token/logout/    → Logout (revoca refresh token)
- POST /api/token/revoke/    → Revoca refresh tokens; access expira según su vigencia
- POST /api/password/reset/  → Solicita reset de password
- POST /api/password/reset/confirm/  → Confirma reset de password
"""

from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

import hashlib
import hmac
import secrets
from django.db import transaction
from rest_framework_simplejwt.tokens import AccessToken
import logging
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import CustomTokenObtainPairSerializer, SessionTokenRefreshSerializer
from neorx.models import log_audit

User = get_user_model()


@method_decorator(ratelimit(key="ip", rate="5/m", block=True), name="post")
class CustomTokenObtainPairView(TokenObtainPairView):
    """Login con rate limiting: 5 intentos por minuto por IP."""
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            log_audit(request, action="login_failed", resource_type="usuario")
            raise
        # Auditar login exitoso
        if response.status_code == 200:
            try:
                user = User.objects.get(pk=AccessToken(response.data['access'])['user_id'])
                log_audit(
                    request,
                    action="login",
                    resource_type="usuario",
                    resource_id=str(user.pk),
                    after={"username": user.username, "rol": user.rol},
                    metadata={"ip": request.META.get('REMOTE_ADDR')},
                )
            except User.DoesNotExist:
                pass
        return response


@method_decorator(ratelimit(key="ip", rate="20/m", block=True), name="post")
class CustomTokenRefreshView(TokenRefreshView):
    """Refresh token con rate limiting: 20 requests por minuto por IP."""
    serializer_class = SessionTokenRefreshSerializer


class LogoutView(APIView):
    """
    POST /api/token/logout/

    Revoca el refresh token del usuario actual.
    Requiere: refresh token en body o en cookie (según configuración).
    """
    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="ip", rate="10/m", block=True))
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            # Intentar obtener de cookie si está configurado
            refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response(
                {"error": "Se requiere refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            if str(token["user_id"]) != str(request.user.pk):
                return Response({"error": "Token no pertenece al usuario."}, status=400)
            token.blacklist()

            # Auditar logout
            log_audit(
                request,
                action="logout",
                resource_type="usuario",
                resource_id=str(request.user.pk),
                metadata={"method": "token_blacklist"},
            )

            return Response({"message": "Logout exitoso. Token revocado."})
        except TokenError:
            return Response(
                {"error": "Token inválido o ya revocado."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class RevokeTokensView(APIView):
    """
    POST /api/token/revoke/

    Revoca todos los refresh tokens del usuario actual.
    Útil para "logout from all devices".
    """
    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="ip", rate="5/m", block=True))
    def post(self, request):
        try:
            # Invalidar todos los refresh tokens del usuario
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

            user_tokens = OutstandingToken.objects.filter(user=request.user)
            count = 0
            for token in user_tokens:
                try:
                    BlacklistedToken.objects.get_or_create(token=token)
                    count += 1
                except Exception:
                    pass

            # Auditar revocación masiva
            log_audit(
                request,
                action="update",
                resource_type="usuario",
                resource_id=str(request.user.pk),
                before={"tokens_revocados": count},
                after={"accion": "revocacion_masiva"},
                metadata={"motivo": "logout_all_devices"},
            )

            return Response({
                "message": f"Se revocaron {count} tokens del usuario.",
                "tokens_revocados": count
            })
        except Exception as e:
            return Response(
                {"error": "No se pudieron revocar los tokens."},
                status=status.HTTP_400_BAD_REQUEST,
            )


RESET_CODE_LIFETIME = timedelta(minutes=10)
RESET_MAX_ATTEMPTS = 5


def _reset_digest(user, value):
    """Keyed digest prevents a stolen database hash from enabling offline OTP guesses."""
    return hmac.new(settings.SECRET_KEY.encode(), f"{user.pk}:{value}".encode(), hashlib.sha256).hexdigest()


def _reset_user(email):
    if not isinstance(email, str):
        return None
    email = email.strip()
    if not email or len(email) > 254:
        return None
    matches = list(User.objects.filter(email__iexact=email, is_active=True).order_by('pk')[:2])
    return matches[0] if len(matches) == 1 else None


def _invalid_reset():
    return Response({"error": "Código inválido o vencido. Solicita uno nuevo si es necesario."}, status=400)


class PasswordResetRequestView(APIView):
    """Send a six-digit one-use code only to an active, registered email."""
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="3/m", block=True))
    def post(self, request):
        user = _reset_user(request.data.get("email"))
        if user is None:
            return Response({"error": "El correo no está registrado en una cuenta activa."}, status=404)
        code = f"{secrets.randbelow(1_000_000):06d}"
        with transaction.atomic():
            locked = User.objects.select_for_update().get(pk=user.pk)
            locked.password_reset_token = _reset_digest(locked, code)
            locked.password_reset_expires = timezone.now() + RESET_CODE_LIFETIME
            locked.password_reset_attempts = 0
            locked.password_reset_verified = False
            locked.save(update_fields=["password_reset_token", "password_reset_expires", "password_reset_attempts", "password_reset_verified"])
        try:
            send_mail(
                subject="Código de recuperación - Neo RX",
                message=(f"Hola {user.get_full_name() or user.username},\n\n"
                         f"Tu código de recuperación es: {code}\n"
                         "Vence en 10 minutos y solo puede usarse una vez.\n"
                         "Si no solicitaste el cambio, ignora este correo.\n"),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            User.objects.filter(pk=user.pk, password_reset_token=_reset_digest(user, code)).update(
                password_reset_token=None, password_reset_expires=None,
                password_reset_attempts=0, password_reset_verified=False,
            )
            logging.getLogger("neorx.request").error("No se pudo enviar correo de recuperación.")
            return Response({"error": "No se pudo enviar el código. Intenta nuevamente más tarde."}, status=503)
        log_audit(request, action="create", resource_type="password_reset", resource_id=str(user.pk),
                  metadata={"method": "email_code"})
        return Response({"message": "Enviamos un código de seis dígitos al correo registrado."})


class PasswordResetVerifyView(APIView):
    """Exchange a valid OTP for an opaque, short-lived reset proof."""
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="5/m", block=True))
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
            return _invalid_reset()
        with transaction.atomic():
            user = _reset_user(email)
            if user is None:
                return _invalid_reset()
            user = User.objects.select_for_update().get(pk=user.pk)
            expired = not user.password_reset_expires or user.password_reset_expires <= timezone.now()
            exhausted = user.password_reset_attempts >= RESET_MAX_ATTEMPTS
            valid = bool(user.password_reset_token and not user.password_reset_verified and not expired and not exhausted
                         and hmac.compare_digest(user.password_reset_token, _reset_digest(user, code)))
            if not valid:
                if user.password_reset_token and not user.password_reset_verified:
                    user.password_reset_attempts += 1
                    if user.password_reset_attempts >= RESET_MAX_ATTEMPTS or expired:
                        user.password_reset_token = None
                        user.password_reset_expires = None
                    user.save(update_fields=["password_reset_attempts", "password_reset_token", "password_reset_expires"])
                return _invalid_reset()
            proof = secrets.token_urlsafe(32)
            user.password_reset_token = _reset_digest(user, proof)
            user.password_reset_verified = True
            user.password_reset_attempts = 0
            user.save(update_fields=["password_reset_token", "password_reset_verified", "password_reset_attempts"])
        return Response({"reset_proof": proof, "message": "Código verificado. Puedes crear una contraseña nueva."})


class PasswordResetConfirmView(APIView):
    """Change password only with the proof obtained from OTP verification."""
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="5/m", block=True))
    def post(self, request):
        email = request.data.get("email")
        proof = request.data.get("reset_proof")
        new_password = request.data.get("new_password")
        if not isinstance(proof, str) or not proof or not isinstance(new_password, str) or not new_password:
            return Response({"error": "Verifica el código e ingresa una contraseña nueva."}, status=400)
        with transaction.atomic():
            user = _reset_user(email)
            if user is None:
                return _invalid_reset()
            user = User.objects.select_for_update().get(pk=user.pk)
            if (not user.password_reset_verified or not user.password_reset_token or
                    not user.password_reset_expires or user.password_reset_expires <= timezone.now() or
                    not hmac.compare_digest(user.password_reset_token, _reset_digest(user, proof))):
                return _invalid_reset()
            try:
                validate_password(new_password, user=user)
            except ValidationError as exc:
                return Response({"error": exc.messages}, status=400)
            user.set_password(new_password)
            user.password_reset_token = None
            user.password_reset_expires = None
            user.password_reset_verified = False
            user.password_reset_attempts = 0
            user.save(update_fields=["password", "password_reset_token", "password_reset_expires", "password_reset_verified", "password_reset_attempts"])
        log_audit(request, action="update", resource_type="usuario", resource_id=str(user.pk),
                  metadata={"method": "password_reset_code"})
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)
        return Response({"message": "Contraseña actualizada. Inicia sesión con tu nueva contraseña."})
