"""
Unit tests for the service health check endpoint.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class HealthCheckTests(APITestCase):
    def test_health_check_endpoint(self) -> None:
        url = reverse("health_check")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "uno-backend")
        self.assertEqual(data["checks"]["database"], "healthy")
