from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class KaziForceUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("KaziForce", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("KaziForce", {"fields": ("email", "role")}),)
    list_display = ("username", "email", "role", "is_staff", "is_active")
