"""Shared administration presentation and read-only recruitment monitoring."""

from django.contrib.admin import AdminSite, ModelAdmin


class ReadOnlyAdmin(ModelAdmin):
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class KaziForceAdminSite(AdminSite):
    site_header = "KaziForce administration"
    site_title = "KaziForce Admin"
    index_title = "Overview"
    index_template = "admin/overview.html"

    def login(self, request, extra_context=None):
        # Share the staged password/code flow; Django's direct staff login would
        # otherwise establish an authenticated session before email verification.
        from accounts.views import SignInView

        request.current_app = self.name
        return SignInView.as_view(
            template_name="admin/login.html",
            authentication_form=self.login_form,
            extra_context={
                **self.each_context(request),
                "title": "Log in",
                "subtitle": None,
                "app_path": request.get_full_path(),
                **(extra_context or {}),
            },
        )(request)

    @property
    def login_form(self):
        from accounts.admin_forms import AdminEmailAuthenticationForm

        return AdminEmailAuthenticationForm

    def index(self, request, extra_context=None):
        from accounts.admin_overview import overview_context

        context = {**(extra_context or {}), **overview_context(request.user)}
        return super().index(request, extra_context=context)
