from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from pages.presentation import public_text


@admin.register(User)
class KaziForceUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("KaziForce", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("KaziForce", {"fields": ("email", "role")}),
    )
    list_display = ("display_name", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name", "username")

    @admin.display(description="Name", ordering="first_name")
    def display_name(self, obj):
        return public_text(obj.get_full_name()) or obj.email
