from django.contrib import admin
from config.admin import ReadOnlyAdmin
from .models import MpesaTransaction


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(ReadOnlyAdmin):
    list_display = [
        "id",
        "booking",
        "amount",
        "masked_phone",
        "payment_status_label",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["checkout_request_id", "booking__title"]
    exclude = ["phone_number"]
    readonly_fields = ["masked_phone"]
