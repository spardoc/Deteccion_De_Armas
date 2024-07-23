from . import views
from django.urls import path

urlpatterns = [
    path('images/', views.post_alert, name='post_alert'),
]