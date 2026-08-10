from django.contrib import admin

from apps.dashboard.models import NotificationDispatchLog, NotificationTopic


@admin.register(NotificationTopic)
class NotificationTopicAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "active", "email_enabled", "in_app_enabled", "send_time", "frequency", "last_sent_at")
    list_filter = ("active", "email_enabled", "in_app_enabled", "frequency")
    search_fields = ("code", "name", "description")
    filter_horizontal = ("users",)


@admin.register(NotificationDispatchLog)
class NotificationDispatchLogAdmin(admin.ModelAdmin):
    list_display = ("event_code", "subject", "status", "attempts", "processed_at", "created_at")
    list_filter = ("event_code", "status", "created_at")
    search_fields = ("subject", "recipients", "error")
    readonly_fields = ("created_at", "processed_at")
