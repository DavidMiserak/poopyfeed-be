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


class NapCreateView(TrackingCreateView):
    model = Nap
    form_class = NapForm
    template_name = "naps/nap_form.html"
    success_url_name = URL_NAP_LIST


class NapUpdateView(TrackingUpdateView):
    model = Nap
    form_class = NapForm
    template_name = "naps/nap_form.html"
    success_url_name = URL_NAP_LIST


class NapDeleteView(TrackingDeleteView):
    model = Nap
    template_name = "naps/nap_confirm_delete.html"
    success_url_name = URL_NAP_LIST
