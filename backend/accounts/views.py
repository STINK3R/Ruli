from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from . import kyc
from .serializers import RegisterSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    """Вход по паролю с лимитом попыток — против подбора пароля."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        user = self.request.user
        user.refresh_from_db()  # статус «Рули ID» мог измениться в соседнем запросе модератора
        return user


class PhoneSendCodeView(APIView):
    """Отправить код подтверждения на номер из профиля (не чаще раза в минуту)."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "phone_code"

    def post(self, request):
        return Response(kyc.send_phone_code(request.user))


class PhoneConfirmView(APIView):
    def post(self, request):
        user = kyc.confirm_phone_code(request.user, request.data.get("code"))
        return Response(UserSerializer(user).data)
