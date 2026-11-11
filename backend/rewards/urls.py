from django.urls import path

from .views import HistoryView, LeaderboardView, RewardsView

urlpatterns = [
    path("", RewardsView.as_view(), name="rewards"),
    path("history/", HistoryView.as_view(), name="rewards-history"),
    path("leaderboard/", LeaderboardView.as_view(), name="rewards-leaderboard"),
]
