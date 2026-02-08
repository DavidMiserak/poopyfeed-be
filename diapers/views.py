from children.tracking_views import (
    TrackingCreateView,
    TrackingDeleteView,
    TrackingListView,
    TrackingUpdateView,
)

from .forms import DiaperChangeForm
from .models import DiaperChange

URL_DIAPER_LIST = "diapers:diaper_list"


class DiaperChangeListView(TrackingListView):
    model = DiaperChange
    template_name = "diapers/diaperchange_list.html"
    context_object_name = "diaper_changes"


class DiaperChangeCreateView(TrackingCreateView):
    model = DiaperChange
    form_class = DiaperChangeForm
    template_name = "diapers/diaperchange_form.html"
    success_url_name = URL_DIAPER_LIST


class DiaperChangeUpdateView(TrackingUpdateView):
    model = DiaperChange
    form_class = DiaperChangeForm
    template_name = "diapers/diaperchange_form.html"
    success_url_name = URL_DIAPER_LIST


class DiaperChangeDeleteView(TrackingDeleteView):
    model = DiaperChange
    template_name = "diapers/diaperchange_confirm_delete.html"
    success_url_name = URL_DIAPER_LIST
