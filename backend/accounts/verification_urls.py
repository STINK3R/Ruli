from django.urls import path

from .verification_views import (
    DemoProfileView,
    DocumentView,
    LivenessFramesView,
    LivenessStartView,
    RequirementsView,
    SubmitView,
    VerificationView,
    WithdrawConsentView,
)

urlpatterns = [
    path("", VerificationView.as_view(), name="verification"),
    path("requirements/", RequirementsView.as_view(), name="verification-requirements"),
    path("documents/<str:kind>/", DocumentView.as_view(), name="verification-document"),
    path("submit/", SubmitView.as_view(), name="verification-submit"),
    path("liveness/", LivenessStartView.as_view(), name="verification-liveness"),
    path("liveness/<int:pk>/", LivenessFramesView.as_view(), name="verification-liveness-frames"),
    path("demo-profile/", DemoProfileView.as_view(), name="verification-demo-profile"),
    path("consent/withdraw/", WithdrawConsentView.as_view(), name="verification-withdraw"),
]
