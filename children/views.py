from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ChildForm
from .mixins import ChildEditMixin, ChildOwnerMixin
from .models import Child, ChildShare, ShareInvite

URL_CHILD_LIST = "children:child_list"
URL_CHILD_SHARING = "children:child_sharing"


class ChildListView(LoginRequiredMixin, ListView):
    model = Child
    template_name = "children/child_list.html"
    context_object_name = "children"

    def get_queryset(self):
        return (
            Child.objects.filter(
                Q(parent=self.request.user) | Q(shares__user=self.request.user)
            )
            .prefetch_related("shares__user")
            .distinct()
            .annotate(
                last_diaper_change=Max("diaper_changes__changed_at"),
                last_nap=Max("naps__napped_at"),
                last_feeding=Max("feedings__fed_at"),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add role info for each child
        children_with_roles = []
        for child in context["children"]:
            children_with_roles.append(
                {
                    "child": child,
                    "role": child.get_user_role(self.request.user),
                    "can_edit": child.can_edit(self.request.user),
                    "is_owner": child.parent == self.request.user,
                }
            )
        context["children_with_roles"] = children_with_roles
        return context


class ChildCreateView(LoginRequiredMixin, CreateView):
    model = Child
    form_class = ChildForm
    template_name = "children/child_form.html"
    success_url = reverse_lazy(URL_CHILD_LIST)

    def form_valid(self, form):
        form.instance.parent = self.request.user
        return super().form_valid(form)


class ChildUpdateView(ChildEditMixin, UpdateView):
    model = Child
    form_class = ChildForm
    template_name = "children/child_form.html"
    success_url = reverse_lazy(URL_CHILD_LIST)

    def get_queryset(self):
        # Allow editing by owner or co-parent
        # Prefetch shares to avoid N+1 queries if form accesses role info
        return Child.objects.filter(
            Q(parent=self.request.user)
            | Q(shares__user=self.request.user, shares__role=ChildShare.Role.CO_PARENT)
        ).prefetch_related("shares__user").distinct()


class ChildDeleteView(ChildOwnerMixin, DeleteView):
    model = Child
    template_name = "children/child_confirm_delete.html"
    success_url = reverse_lazy(URL_CHILD_LIST)

    def get_queryset(self):
        # Only owners can delete
        return Child.objects.filter(parent=self.request.user)


class ChildSharingView(ChildOwnerMixin, DetailView):
    """Manage sharing for a child - owner only."""

    model = Child
    template_name = "children/child_sharing.html"
    context_object_name = "child"

    def get_queryset(self):
        return Child.objects.filter(parent=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["shares"] = self.object.shares.select_related("user")
        context["invites"] = self.object.invites.all()
        context["roles"] = ChildShare.Role.choices
        return context


class CreateInviteView(ChildOwnerMixin, View):
    """Create a new sharing invite - owner only."""

    def post(self, request, pk):
        role = request.POST.get("role", ChildShare.Role.CAREGIVER)

        # Validate role
        if role not in [ChildShare.Role.CO_PARENT, ChildShare.Role.CAREGIVER]:
            role = ChildShare.Role.CAREGIVER

        ShareInvite.objects.create(
            child=self.child,
            role=role,
            created_by=request.user,
        )

        messages.success(request, f"Invite link created for {self.child.name}")
        return redirect(URL_CHILD_SHARING, pk=pk)


class RevokeAccessView(ChildOwnerMixin, View):
    """Revoke a user's access to child - owner only."""

    def post(self, request, pk, share_pk):
        share = get_object_or_404(ChildShare, pk=share_pk, child=self.child)

        user_email = share.user.email
        share.delete()

        messages.success(request, f"Access revoked for {user_email}")
        return redirect(URL_CHILD_SHARING, pk=pk)


class ToggleInviteView(ChildOwnerMixin, View):
    """Toggle invite active status - owner only."""

    def post(self, request, pk, invite_pk):
        invite = get_object_or_404(ShareInvite, pk=invite_pk, child=self.child)

        invite.is_active = not invite.is_active
        invite.save()

        status = "activated" if invite.is_active else "deactivated"
        messages.success(request, f"Invite link {status}")
        return redirect(URL_CHILD_SHARING, pk=pk)


class DeleteInviteView(ChildOwnerMixin, View):
    """Delete an invite link - owner only."""

    def post(self, request, pk, invite_pk):
        invite = get_object_or_404(ShareInvite, pk=invite_pk, child=self.child)

        invite.delete()

        messages.success(request, "Invite link deleted")
        return redirect(URL_CHILD_SHARING, pk=pk)


class AcceptInviteView(LoginRequiredMixin, View):
    """Accept an invite link - any authenticated user."""

    def get(self, request, token):
        invite = get_object_or_404(ShareInvite, token=token, is_active=True)

        # Check if user is already the owner
        if invite.child.parent == request.user:
            messages.warning(request, "You are already the owner of this child")
            return redirect(URL_CHILD_LIST)

        # Handle potential race condition with get_or_create
        with transaction.atomic():
            try:
                share, created = ChildShare.objects.get_or_create(
                    child=invite.child,
                    user=request.user,
                    defaults={
                        "role": invite.role,
                        "created_by": invite.created_by,
                    },
                )
            except IntegrityError:
                # Race condition: another request created the share concurrently
                # Fetch the existing share
                share = ChildShare.objects.get(child=invite.child, user=request.user)
                created = False

        if created:
            role_display = dict(ChildShare.Role.choices).get(invite.role, invite.role)
            messages.success(
                request,
                f"You now have {role_display} access to {invite.child.name}",
            )
        else:
            messages.info(
                request,
                f"You already have {share.get_role_display()} "
                f"access to {invite.child.name}",
            )
        return redirect(URL_CHILD_LIST)
