from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.views import View
from django.views.generic import TemplateView


class HomePageView(TemplateView):
    template_name = "pages/home.html"


class OfflinePageView(TemplateView):
    template_name = "pwa/offline.html"


class ServiceWorkerView(View):
    """Serve service worker at root scope with correct headers."""

    def get(self, request):
        sw_path = Path(settings.BASE_DIR) / "static" / "js" / "service-worker.js"
        content = sw_path.read_text()
        response = HttpResponse(content, content_type="application/javascript")
        response["Service-Worker-Allowed"] = "/"
        return response
