from django.urls import path

from .views import HomePageView, OfflinePageView, ServiceWorkerView

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("offline/", OfflinePageView.as_view(), name="offline"),
    path("sw.js", ServiceWorkerView.as_view(), name="service_worker"),
]
