from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.dashboard.api.serializers.index import NotificationTopicSerializer
from apps.dashboard.api.services.operational_center import (
    process_pending_notifications,
    queue_topic_email,
    send_topic_email,
)
from apps.dashboard.models import INTERNAL_RECIPIENT_ROLE, NotificationDispatchLog, NotificationTopic
from apps.misc.api.models.companies.index import Empresa
from apps.users.api.models.index import User


class NotificationTopicContractTests(TestCase):
    def test_event_types_endpoint_is_registered_and_reports_availability(self):
        user = User.objects.create_user(
            email="notifications-admin@example.com",
            password="test-password",
            is_active=True,
        )
        NotificationTopic.objects.create(
            code=NotificationTopic.EventCode.DAILY_DIGEST,
            name="Resumen diario",
        )
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(reverse("notification-topics-event-types"))

        self.assertEqual(response.status_code, 200)
        event_types = {item["value"]: item for item in response.json()}
        self.assertTrue(event_types[NotificationTopic.EventCode.DAILY_DIGEST]["configured"])
        self.assertFalse(event_types[NotificationTopic.EventCode.OVERDUE]["configured"])

    def test_missing_topic_is_not_created_when_event_is_emitted(self):
        result = send_topic_email(
            NotificationTopic.EventCode.NEW_CLIENT_BATCH,
            "Nuevo lote",
            "Mensaje de prueba",
        )

        self.assertFalse(result["sent"])
        self.assertEqual(result["reason"], "topic_disabled")
        self.assertFalse(NotificationTopic.objects.exists())

    def test_topic_can_be_created_explicitly(self):
        serializer = NotificationTopicSerializer(data={
            "code": NotificationTopic.EventCode.DAILY_DIGEST,
            "name": "Resumen de las 7",
            "active": True,
            "email_enabled": True,
            "in_app_enabled": False,
            "frequency": "daily",
            "send_time": "07:00:00",
            "roles": [],
            "external_emails": ["laboratorio@example.com"],
            "users": [],
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        topic = serializer.save()
        self.assertEqual(topic.name, "Resumen de las 7")
        self.assertEqual(topic.send_time.strftime("%H:%M"), "07:00")

    def test_external_recipient_must_be_a_valid_email(self):
        serializer = NotificationTopicSerializer(data={
            "code": NotificationTopic.EventCode.DAILY_DIGEST,
            "name": "Resumen diario",
            "external_emails": ["esto-no-es-un-correo"],
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("external_emails", serializer.errors)

    def test_internal_global_oil_group_excludes_client_users(self):
        internal = User.objects.create_user(email="interno@globaloil.test", is_active=True)
        company = Empresa.objects.create(nombre="Cliente externo")
        User.objects.create_user(
            email="cliente@example.com",
            is_active=True,
            empresa=company,
            role=User.Role.EMPRESA,
        )
        topic = NotificationTopic.objects.create(
            code=NotificationTopic.EventCode.NEW_CLIENT_BATCH,
            name="Nuevo lote",
            roles=[INTERNAL_RECIPIENT_ROLE],
        )

        self.assertEqual(topic.resolved_recipient_emails(), [internal.email])

    @patch("apps.dashboard.api.views.index.send_mail")
    def test_test_email_endpoint_uses_resolved_recipients(self, send_mail_mock):
        user = User.objects.create_user(
            email="notifications-owner@example.com",
            password="test-password",
            is_active=True,
        )
        topic = NotificationTopic.objects.create(
            code=NotificationTopic.EventCode.NEW_CLIENT_BATCH,
            name="Nuevo lote",
            external_emails=["laboratorio@example.com"],
        )
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(reverse("notification-topics-test-email", args=[topic.pk]))

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["recipients"], ["laboratorio@example.com"])
        send_mail_mock.assert_called_once()
        self.assertTrue(NotificationDispatchLog.objects.filter(payload__test=True, status="sent").exists())

    def test_event_code_is_immutable_after_creation(self):
        topic = NotificationTopic.objects.create(
            code=NotificationTopic.EventCode.DAILY_DIGEST,
            name="Resumen diario",
        )
        serializer = NotificationTopicSerializer(
            topic,
            data={"code": NotificationTopic.EventCode.OVERDUE},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_delete_deactivates_topic_without_removing_it(self):
        user = User.objects.create_user(
            email="mail-list-admin@example.com",
            password="test-password",
            is_active=True,
        )
        topic = NotificationTopic.objects.create(
            code=NotificationTopic.EventCode.DAILY_DIGEST,
            name="Resumen diario",
        )
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.delete(reverse("notification-topics-detail", args=[topic.pk]))

        self.assertEqual(response.status_code, 200)
        topic.refresh_from_db()
        self.assertFalse(topic.active)
        self.assertTrue(NotificationTopic.objects.filter(pk=topic.pk).exists())

    def test_operational_email_is_queued_without_contacting_smtp(self):
        NotificationTopic.objects.create(
            code=NotificationTopic.EventCode.NEW_CLIENT_BATCH,
            name="Nuevo lote",
            external_emails=["laboratorio@example.com"],
        )

        with patch("apps.dashboard.api.services.operational_center.send_mail") as send_mail_mock:
            result = queue_topic_email(
                NotificationTopic.EventCode.NEW_CLIENT_BATCH,
                "Lote L1",
                "Mensaje",
                {"batch_id": "L1"},
            )

        self.assertTrue(result["queued"])
        send_mail_mock.assert_not_called()
        dispatch = NotificationDispatchLog.objects.get()
        self.assertEqual(dispatch.status, "pending")
        self.assertEqual(dispatch.message, "Mensaje")

    @patch("apps.dashboard.api.services.operational_center.send_mail")
    def test_pending_notification_can_be_processed(self, send_mail_mock):
        topic = NotificationTopic.objects.create(
            code=NotificationTopic.EventCode.NEW_CLIENT_BATCH,
            name="Nuevo lote",
            external_emails=["laboratorio@example.com"],
        )
        NotificationDispatchLog.objects.create(
            topic=topic,
            event_code=topic.code,
            subject="Lote L1",
            message="Mensaje",
            recipients=["laboratorio@example.com"],
            status="pending",
        )

        summary = process_pending_notifications()

        self.assertEqual(summary, {"processed": 1, "sent": 1, "failed": 0})
        dispatch = NotificationDispatchLog.objects.get()
        self.assertEqual(dispatch.status, "sent")
        self.assertEqual(dispatch.attempts, 1)
        self.assertIsNotNone(dispatch.processed_at)
        send_mail_mock.assert_called_once()
