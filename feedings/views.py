from children.tracking_views import (
    TrackingCreateView,
    TrackingDeleteView,
    TrackingListView,
    TrackingUpdateView,
)

from .forms import FeedingForm
from .models import Feeding

URL_FEEDING_LIST = "feedings:feeding_list"


class FeedingListView(TrackingListView):
    model = Feeding
    template_name = "feedings/feeding_list.html"
    context_object_name = "feedings"


class FeedingCreateView(TrackingCreateView):
    model = Feeding
    form_class = FeedingForm
    template_name = "feedings/feeding_form.html"
    success_url_name = URL_FEEDING_LIST


class FeedingUpdateView(TrackingUpdateView):
    model = Feeding
    form_class = FeedingForm
    template_name = "feedings/feeding_form.html"
    success_url_name = URL_FEEDING_LIST


class FeedingDeleteView(TrackingDeleteView):
    model = Feeding
    template_name = "feedings/feeding_confirm_delete.html"
    success_url_name = URL_FEEDING_LIST
