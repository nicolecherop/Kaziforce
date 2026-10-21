from django.urls import path
from . import views

app_name = "matching"
urlpatterns = [path("search/", views.search_skills, name="skill_search")]
