import io
import json
from unittest.mock import patch

import pytest

import server


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def _upload(client, filename: str, content: bytes):
    return client.post(
        "/api/parse-upload",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def test_rejects_missing_file(client):
    res = client.post("/api/parse-upload", data={}, content_type="multipart/form-data")
    assert res.status_code == 400


def test_rejects_unsupported_extension(client, clean_pdf_bytes):
    res = _upload(client, "cv.txt", clean_pdf_bytes)
    assert res.status_code == 400


def test_extraction_failure_returns_422(client, corrupt_file_bytes):
    res = _upload(client, "cv.pdf", corrupt_file_bytes)
    assert res.status_code == 422


def test_successful_sectioning(client, clean_pdf_bytes):
    good_json = json.dumps(
        {"sections": [{"name": "Experience", "bullets": ["did a thing"]}]}
    )
    with patch("server.chat", return_value=good_json):
        res = _upload(client, "cv.pdf", clean_pdf_bytes)

    assert res.status_code == 200
    data = res.get_json()
    assert data["sections"] == [{"name": "Experience", "bullets": ["did a thing"]}]
    assert data["degraded"] is False
    assert data["source_filename"] == "cv.pdf"


def test_sectioning_falls_back_after_two_bad_responses(client, clean_pdf_bytes):
    with patch("server.chat", return_value="not json"):
        res = _upload(client, "cv.pdf", clean_pdf_bytes)

    assert res.status_code == 200
    data = res.get_json()
    assert data["degraded"] is True
    assert data["sections"][0]["name"] == "Full text"


def test_foundry_unavailable_returns_503(client, clean_pdf_bytes):
    with patch("server.chat", side_effect=server.FoundryUnavailable("down")):
        res = _upload(client, "cv.pdf", clean_pdf_bytes)

    assert res.status_code == 503
