from django.urls import path

from .views.index import NotificationDispatchLogViewSet, NotificationTopicViewSet, OperationalCenterViewSet


urlpatterns = [
    path("dashboard/operational-center/", OperationalCenterViewSet.as_view({"get": "list"}), name="operational-center"),
    path("dashboard/operational-center/send-daily-digest/", OperationalCenterViewSet.as_view({"post": "send_daily_digest"}), name="operational-center-send-daily-digest"),
    path("dashboard/notification-topics/", NotificationTopicViewSet.as_view({"get": "list", "post": "create"}), name="notification-topics-list"),
    path("dashboard/notification-topics/event-types/", NotificationTopicViewSet.as_view({"get": "event_types"}), name="notification-topics-event-types"),
    path("dashboard/notification-topics/roles/", NotificationTopicViewSet.as_view({"get": "roles"}), name="notification-topics-roles"),
    path("dashboard/notification-topics/users/", NotificationTopicViewSet.as_view({"get": "users"}), name="notification-topics-users"),
    path("dashboard/notification-topics/<int:pk>/", NotificationTopicViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="notification-topics-detail"),
    path("dashboard/notification-topics/<int:pk>/test-email/", NotificationTopicViewSet.as_view({"post": "test_email"}), name="notification-topics-test-email"),
    path("dashboard/notification-dispatches/", NotificationDispatchLogViewSet.as_view({"get": "list"}), name="notification-dispatches-list"),
]
