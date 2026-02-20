import pytest


class TestHealthEndpoint:
    """헬스체크 엔드포인트 테스트"""

    def test_health_returns_ok(self, client):
        """GET /health 정상 응답"""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSentryWebhook:
    """Sentry 웹훅 엔드포인트 테스트"""

    def test_sentry_webhook_creates_job(self, client, sentry_payload):
        """POST /webhook/sentry → Job 생성"""
        response = client.post("/webhook/sentry", json=sentry_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"
        assert data["source"] == "sentry"
        assert data["issue_id"] == "7241469116"
        assert data["title"] == "ZeroDivisionError: division by zero"
        assert "job_id" in data

    def test_sentry_webhook_duplicate_returns_duplicate(self, client, sentry_payload):
        """동일 issue_id로 재요청 시 duplicate 반환"""
        # 첫 번째 요청
        response1 = client.post("/webhook/sentry", json=sentry_payload)
        assert response1.json()["status"] == "created"

        # 두 번째 요청 (동일 payload)
        response2 = client.post("/webhook/sentry", json=sentry_payload)
        assert response2.status_code == 200
        data = response2.json()
        assert data["status"] == "duplicate"
        assert data["issue_id"] == "7241469116"

    def test_sentry_webhook_minimal_payload(self, client, sentry_payload_minimal):
        """최소 payload 처리"""
        response = client.post("/webhook/sentry", json=sentry_payload_minimal)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"
        assert data["issue_id"] == "abc123"

    def test_sentry_webhook_invalid_payload(self, client):
        """잘못된 payload 처리"""
        response = client.post("/webhook/sentry", json={"invalid": "payload"})

        assert response.status_code == 422  # Validation Error
