from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission

from apps.dashboard.api.serializers.index import (
    NotificationDispatchLogSerializer,
    NotificationTopicSerializer,
)
from apps.dashboard.api.services.operational_center import (
    build_operational_center,
    send_daily_digest,
)
from apps.dashboard.models import INTERNAL_RECIPIENT_ROLE, NotificationDispatchLog, NotificationTopic
from apps.users.api.models.index import User


class OperationalCenterViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response(build_operational_center(request.user, request.query_params))

    @action(detail=False, methods=["post"], url_path="send-daily-digest")
    def send_daily_digest(self, request):
        result = send_daily_digest(request.user)
        http_status = status.HTTP_200_OK if result.get("sent") else status.HTTP_202_ACCEPTED
        return Response(result, status=http_status)


class NotificationTopicViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    serializer_class = NotificationTopicSerializer
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "config_tecnica.ver",
        "retrieve": "config_tecnica.ver",
        "event_types": "config_tecnica.ver",
        "roles": "config_tecnica.ver",
        "users": "config_tecnica.ver",
        "create": "config_tecnica.editar",
        "update": "config_tecnica.editar",
        "partial_update": "config_tecnica.editar",
        "destroy": "config_tecnica.editar",
        "restore": "config_tecnica.editar",
        "test_email": "config_tecnica.editar",
    }

    def get_queryset(self):
        return NotificationTopic.objects.prefetch_related("users").all()

    def destroy(self, request, *args, **kwargs):
        """Preserve configuration and dispatch history; DELETE deactivates."""
        topic = self.get_object()
        if topic.active:
            topic.active = False
            topic.save(update_fields=["active", "updated_at"])
        return Response(self.get_serializer(topic).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        topic = self.get_object()
        topic.active = True
        topic.save(update_fields=["active", "updated_at"])
        return Response(self.get_serializer(topic).data)

    @action(detail=False, methods=["get"], url_path="event-types")
    def event_types(self, request):
        configured = set(NotificationTopic.objects.values_list("code", flat=True))
        implemented_modes = {
            NotificationTopic.EventCode.DAILY_DIGEST: "daily",
            NotificationTopic.EventCode.NEW_CLIENT_BATCH: "event",
            NotificationTopic.EventCode.DUE_SOON: "daily",
            NotificationTopic.EventCode.OVERDUE: "daily",
        }
        return Response([
            {
                "value": value,
                "label": label,
                "configured": value in configured,
                "implemented": value in implemented_modes,
                "mode": implemented_modes.get(value),
            }
            for value, label in NotificationTopic.EventCode.choices
        ])

    @action(detail=False, methods=["get"], url_path="roles")
    def roles(self, request):
        return Response([
            {
                "value": INTERNAL_RECIPIENT_ROLE,
                "label": "Equipo interno de Global Oil",
                "description": "Usuarios activos de Global Oil, sin incluir clientes.",
            },
            *[{"value": value, "label": label} for value, label in User.Role.choices],
        ])

    @action(detail=False, methods=["get"], url_path="users")
    def users(self, request):
        users = User.objects.filter(is_active=True).order_by("email")
        return Response([
            {
                "id": item.id,
                "email": item.email,
                "name": item.get_full_name() or item.email,
                "role": item.role,
            }
            for item in users
        ])

    @action(detail=True, methods=["post"], url_path="test-email")
    def test_email(self, request, pk=None):
        topic = self.get_object()
        recipients = topic.resolved_recipient_emails()
        if not recipients:
            return Response(
                {"detail": "Agregue al menos un destinatario antes de enviar la prueba."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subject = f"[PRUEBA] {topic.name}"
        message = (
            "Este es un correo de prueba de Global Oil.\n\n"
            f"Regla: {topic.name}\n"
            f"Evento: {topic.get_code_display()}\n"
            "La configuración de destinatarios funciona correctamente."
        )
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
            dispatch_status = "sent"
            error = ""
        except Exception as exc:
            dispatch_status = "failed"
            error = str(exc)

        NotificationDispatchLog.objects.create(
            topic=topic,
            event_code=topic.code,
            subject=subject,
            message=message,
            recipients=recipients,
            status=dispatch_status,
            attempts=1,
            error=error,
            payload={"test": True, "requested_by": request.user.pk},
            processed_at=timezone.now(),
        )
        if error:
            return Response(
                {"detail": "No se pudo enviar el correo de prueba.", "error": error},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"detail": "Correo de prueba enviado.", "recipients": recipients})


class NotificationDispatchLogViewSet(ActionPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationDispatchLogSerializer
    permission_classes = [IsAuthenticated, HasSecurityPermission]
    permission_action_map = {"list": "config_tecnica.ver", "retrieve": "config_tecnica.ver"}
    queryset = NotificationDispatchLog.objects.select_related("topic").all()
