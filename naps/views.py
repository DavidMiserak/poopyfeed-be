from children.tracking_views import (
    TrackingCreateView,
    TrackingDeleteView,
    TrackingListView,
    TrackingUpdateView,
)

from .forms import NapForm
from .models import Nap

URL_NAP_LIST = "naps:nap_list"


class NapListView(TrackingListView):
    model = Nap
    template_name = "naps/nap_list.html"
    context_object_name = "naps"
    date_field = "napped_at"


class NapCreateView(TrackingCreateView):
    model = Nap
    form_class = NapForm
    template_name = "naps/nap_form.html"
    success_url_name = URL_NAP_LIST

    def get_initial(self):
        """Pre-fill nap times from query params (used by timeline gap button)."""
        initial = super().get_initial()
        napped_at = self.request.GET.get("napped_at")
        ended_at = self.request.GET.get("ended_at")
        if napped_at:
            initial["napped_at"] = napped_at
        if ended_at:
            initial["ended_at"] = ended_at
        return initial


class NapUpdateView(TrackingUpdateView):
    model = Nap
    form_class = NapForm
    template_name = "naps/nap_form.html"
    success_url_name = URL_NAP_LIST


class NapDeleteView(TrackingDeleteView):
    model = Nap
    template_name = "naps/nap_confirm_delete.html"
    success_url_name = URL_NAP_LIST
