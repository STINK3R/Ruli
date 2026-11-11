from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import PointsEntry


class RewardsView(APIView):
    """Баланс, ранг, достижения, задания недели и код «Приведи друга»."""

    def get(self, request):
        return Response(services.summary(request.user))


class HistoryView(APIView):
    def get(self, request):
        entries = PointsEntry.objects.filter(user=request.user)[:100]
        return Response(
            [
                {"id": e.id, "amount": e.amount, "kind": e.kind, "title": e.title, "created_at": e.created_at}
                for e in entries
            ]
        )


class LeaderboardView(APIView):
    """Рейтинг виден всем, даже без входа: имя и первая буква фамилии."""

    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        period = request.query_params.get("period", "week")
        if period not in ("week", "month", "all"):
            period = "week"
        me = request.user if request.user.is_authenticated else None
        return Response(services.leaderboard(period, me))
