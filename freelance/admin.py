"""Permission-scoped oversight. Agreement and payment evidence is read-only."""

from django.contrib import admin
from config.admin import ReadOnlyAdmin
from .models import (
    FreelancerProfile,
    FreelanceService,
    FreelanceProject,
    Conversation,
    Message,
    Booking,
    BookingEvent,
    Payment,
    Review,
    ConversationReport,
)


@admin.register(FreelancerProfile)
class FreelancerAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "accepting_bookings", "location", "updated_at"]
    list_filter = ["accepting_bookings", "work_mode"]
    search_fields = ["title", "user__email"]
    readonly_fields = [
        f.name for f in FreelancerProfile._meta.fields if f.name != "accepting_bookings"
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Booking)
class BookingAdmin(ReadOnlyAdmin):
    list_display = ["title", "status", "start_date", "end_date", "total_price"]
    list_filter = ["status"]
    search_fields = ["title", "recruiter_name", "freelancer_name"]


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdmin):
    list_display = ["booking", "kind", "amount", "method", "status", "created_at"]
    list_filter = ["status", "method", "kind"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["booking", "rating", "is_hidden", "created_at"]
    list_filter = ["is_hidden", "rating"]
    readonly_fields = ["booking", "rating", "comment", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConversationReport)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["conversation", "reporter", "is_resolved", "created_at"]
    list_filter = ["is_resolved"]
    readonly_fields = ["conversation", "reporter", "reason", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in [FreelanceService, FreelanceProject, Conversation, Message, BookingEvent]:
    admin.site.register(model, ReadOnlyAdmin)
