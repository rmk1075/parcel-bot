from django.urls import path

from parcel_bot import views

urlpatterns = [
    path("chat/", views.chat),
]
