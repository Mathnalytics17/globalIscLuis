from rest_framework import serializers

from apps.dashboard.models import NotificationDispatchLog, NotificationTopic
from apps.users.api.models.index import User


class NotificationUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "full_name"]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email


class NotificationTopicSerializer(serializers.ModelSerializer):
    users_info = NotificationUserSerializer(source="users", many=True, read_only=True)
    users = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), many=True, required=False)
    resolved_recipients = serializers.SerializerMethodField()

    class Meta:
        model = NotificationTopic
        fields = [
            "id",
            "code",
            "name",
            "description",
            "active",
            "email_enabled",
            "in_app_enabled",
            "send_time",
            "frequency",
            "roles",
            "external_emails",
            "users",
            "users_info",
            "resolved_recipients",
            "last_sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "last_sent_at"]

    def validate_code(self, value):
        if self.instance and self.instance.code != value:
            raise serializers.ValidationError("El evento no puede cambiarse después de crear la regla.")
        return value

    def validate_external_emails(self, value):
        validator = serializers.EmailField()
        normalized = []
        for email in value or []:
            normalized.append(validator.run_validation(str(email).strip()).lower())
        return list(dict.fromkeys(normalized))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        frequency = attrs.get("frequency", getattr(self.instance, "frequency", "event"))
        send_time = attrs.get("send_time", getattr(self.instance, "send_time", None))
        if frequency == "daily" and not send_time:
            raise serializers.ValidationError({"send_time": "Indique la hora del envío diario."})
        return attrs

    def get_resolved_recipients(self, obj):
        return obj.resolved_recipient_emails()


class NotificationDispatchLogSerializer(serializers.ModelSerializer):
    topic_name = serializers.CharField(source="topic.name", read_only=True)

    class Meta:
        model = NotificationDispatchLog
        fields = [
            "id", "topic", "topic_name", "event_code", "subject", "recipients",
            "status", "attempts", "error", "processed_at", "created_at",
        ]
