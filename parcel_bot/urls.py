from django.urls import path

from parcel_bot import views

urlpatterns = [
    path("", views.index),
    path("chat/", views.chat),
    path("graph/sync/", views.graph_sync),
    path("graph/async/", views.graph_async),
    path("graph/bridge/", views.graph_bridge),
]
