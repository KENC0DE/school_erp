"""P1-22: file storage, validation, signed URLs and thumbnails."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import pytest
from app.errors import ValidationFailed
from core.events.models import Job
from core.files.s3 import S3Config, presign
from core.files.service import generate_thumbnail
from core.files.storage import LocalStorage
from PIL import Image
from sqlalchemy import select


def png_bytes(size: tuple[int, int] = (64, 48), colour: tuple[int, int, int] = (10, 120, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg_bytes(size: tuple[int, int] = (800, 600)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 100, 30)).save(buffer, format="JPEG")
    return buffer.getvalue()


async def upload(
    client,
    headers,
    *,
    name: str = "photo.png",
    data: bytes | None = None,
    content_type: str = "image/png",
    extra: dict | None = None,
):
    body = data if data is not None else png_bytes()
    return await client.post(
        "/api/v1/files",
        files={"file": (name, body, content_type)},
        data=extra or {},
        headers=headers,
    )


async def test_upload_metadata_signed_download_and_audit(client, app, superadmin_headers):
    data = png_bytes()
    response = await upload(
        client,
        superadmin_headers,
        extra={"owner_entity_type": "student", "owner_entity_id": "student-1"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "photo.png"
    assert body["mime"] == "image/png"
    assert body["size_bytes"] == len(data)
    assert body["checksum_sha256"] == hashlib.sha256(data).hexdigest()
    assert body["owner_entity_type"] == "student"
    assert body["owner_entity_id"] == "student-1"
    assert body["is_private"] is True
    assert body["url"].startswith("http://testserver/api/v1/files/content/")
    assert body["thumbnail_job_id"]

    download = await client.get(body["url"])
    assert download.status_code == 200, download.text
    assert download.content == data
    assert download.headers["content-type"] == "image/png"
    assert download.headers["x-content-type-options"] == "nosniff"

    detail = await client.get(f"/api/v1/files/{body['id']}", headers=superadmin_headers)
    assert detail.status_code == 200
    assert detail.json()["checksum_sha256"] == body["checksum_sha256"]

    listed = await client.get(
        "/api/v1/files",
        params={"owner_entity_type": "student", "owner_entity_id": "student-1"},
        headers=superadmin_headers,
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [body["id"]]

    activity = await client.get(
        "/api/v1/audit/activity",
        params={"entity_type": "file"},
        headers=superadmin_headers,
    )
    assert "file.upload" in {item["action"] for item in activity.json()["items"]}

    async with app.state.db.session() as session:
        jobs = (await session.execute(select(Job).where(Job.kind == "files.thumbnail"))).scalars().all()
    assert [job.payload["file_id"] for job in jobs] == [body["id"]]


async def test_signed_links_reject_tampering_and_expiry(client, superadmin_headers):
    body = (await upload(client, superadmin_headers)).json()
    url = body["url"]

    parts = urlsplit(url)
    query = parse_qs(parts.query)
    query["expires"] = ["1"]
    expired = urlunsplit(parts._replace(query=urlencode(query, doseq=True)))
    response = await client.get(expired)
    assert response.status_code == 410
    assert response.json()["error"]["message_key"] == "error.file.expired"

    tampered = url[:-4] + "0000"
    response = await client.get(tampered)
    assert response.status_code == 422
    assert response.json()["error"]["message_key"] == "error.file.invalid_signature"


async def test_upload_validation_rejects_empty_oversize_and_spoofed_files(client, app, superadmin_headers):
    empty = await upload(client, superadmin_headers, name="empty.txt", data=b"", content_type="text/plain")
    assert empty.status_code == 422
    assert empty.json()["error"]["message_key"] == "error.file.empty"

    executable = await upload(
        client,
        superadmin_headers,
        name="virus.exe",
        data=b"MZ...",
        content_type="application/octet-stream",
    )
    assert executable.status_code == 415
    assert executable.json()["error"]["message_key"] == "error.file.unsupported_type"

    spoofed = await upload(
        client,
        superadmin_headers,
        name="notes.pdf",
        data=b"this is not a pdf",
        content_type="application/pdf",
    )
    assert spoofed.status_code == 415
    assert spoofed.json()["error"]["message_key"] == "error.file.content_mismatch"

    wrong_mime = await upload(
        client,
        superadmin_headers,
        name="photo.png",
        data=png_bytes(),
        content_type="text/plain",
    )
    assert wrong_mime.status_code == 415
    assert wrong_mime.json()["error"]["message_key"] == "error.file.content_mismatch"

    app.state.settings.storage_max_upload_bytes = 32
    oversize = await upload(client, superadmin_headers, data=png_bytes((80, 80)))
    assert oversize.status_code == 413
    assert oversize.json()["error"]["message_key"] == "error.file.too_large"


async def test_private_files_are_visible_to_their_uploader_and_managers_only(
    client, app, superadmin_headers, limited_headers
):
    from tests.conftest import create_role, create_user, login

    await create_role(app, "uploader", [("files.upload", "all"), ("ai.use", "all")])
    await create_user(app, "uploader@demo.school", roles=["uploader"])
    uploader_headers = await login(client, "uploader@demo.school")

    private = (await upload(client, uploader_headers)).json()
    assert private["is_private"] is True

    owner = await client.get(f"/api/v1/files/{private['id']}", headers=uploader_headers)
    assert owner.status_code == 200
    stranger = await client.get(f"/api/v1/files/{private['id']}", headers=limited_headers)
    assert stranger.status_code == 403
    manager = await client.get(f"/api/v1/files/{private['id']}", headers=superadmin_headers)
    assert manager.status_code == 200

    listed = await client.get("/api/v1/files", headers=limited_headers)
    assert listed.status_code == 403
    denied = await upload(client, limited_headers)
    assert denied.status_code == 403

    public = (await upload(client, uploader_headers, extra={"is_private": "false"})).json()
    visible = await client.get(f"/api/v1/files/{public['id']}", headers=limited_headers)
    assert visible.status_code == 200

    remove = await client.delete(f"/api/v1/files/{private['id']}", headers=limited_headers)
    assert remove.status_code == 403
    removed = await client.delete(f"/api/v1/files/{private['id']}", headers=uploader_headers)
    assert removed.status_code == 200
    assert removed.json()["deleted"] is True
    assert (await client.get(f"/api/v1/files/{private['id']}", headers=uploader_headers)).status_code == 404
    assert (await client.get(private["url"])).status_code == 404


async def test_thumbnail_job_builds_a_small_jpeg(client, app, superadmin_headers):
    body = (
        await upload(
            client, superadmin_headers, name="large.jpg", data=jpeg_bytes(), content_type="image/jpeg"
        )
    ).json()
    assert body["has_thumbnail"] is False
    assert body["thumbnail_job_id"]

    async with app.state.db.session() as session:
        result = await generate_thumbnail(session, app.state.storage, body["id"])
    assert result["file_id"] == body["id"]
    assert result["thumbnail_key"].endswith(".jpg")

    detail = await client.get(f"/api/v1/files/{body['id']}", headers=superadmin_headers)
    assert detail.json()["has_thumbnail"] is True
    thumbnail_url = detail.json()["thumbnail_url"]
    thumb = await client.get(thumbnail_url)
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(thumb.content)) as image:
        assert image.width <= 320
        assert image.height <= 320

    signed = await client.get(
        f"/api/v1/files/{body['id']}/url",
        params={"thumbnail": "true", "expires_in": 120},
        headers=superadmin_headers,
    )
    assert signed.status_code == 200
    assert signed.json()["expires_in"] == 120
    assert signed.json()["thumbnail"] is True


async def test_non_images_do_not_get_a_thumbnail(client, superadmin_headers):
    body = (
        await upload(
            client,
            superadmin_headers,
            name="notes.txt",
            data="ሰላም\n".encode(),
            content_type="text/plain",
        )
    ).json()
    assert body["has_thumbnail"] is False
    assert body["thumbnail_job_id"] is None
    signed = await client.get(
        f"/api/v1/files/{body['id']}/url",
        params={"thumbnail": "true"},
        headers=superadmin_headers,
    )
    assert signed.status_code == 404
    assert signed.json()["error"]["message_key"] == "error.file.thumbnail_missing"


def test_s3_presigned_urls_are_deterministic_and_scoped():
    config = S3Config(
        endpoint="https://s3.example.com",
        region="eu-west-1",
        bucket="school-files",
        access_key="AKIAEXAMPLE",
        secret_key="secret",
    )
    moment = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
    url = presign(config, "GET", "2026/11/report.pdf", expires_in=600, now=moment)
    assert url.startswith("https://s3.example.com/school-files/2026/11/report.pdf?")
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in url
    assert "X-Amz-Expires=600" in url
    assert "X-Amz-Credential=AKIAEXAMPLE%2F20261117%2Feu-west-1%2Fs3%2Faws4_request" in url
    assert "X-Amz-Signature=" in url

    same = presign(config, "GET", "2026/11/report.pdf", expires_in=600, now=moment)
    assert same == url
    other_key = presign(config, "GET", "2026/11/other.pdf", expires_in=600, now=moment)
    other_method = presign(config, "PUT", "2026/11/report.pdf", expires_in=600, now=moment)
    assert other_key != url
    assert other_method != url

    virtual = S3Config(
        endpoint="https://s3.example.com",
        region="eu-west-1",
        bucket="school-files",
        access_key="AKIAEXAMPLE",
        secret_key="secret",
        path_style=False,
    )
    virtual_url = presign(virtual, "GET", "2026/11/report.pdf", expires_in=600, now=moment)
    assert virtual_url.startswith("https://school-files.s3.example.com/2026/11/report.pdf?")


def test_local_storage_refuses_traversal(tmp_path):
    storage = LocalStorage(tmp_path / "objects", "secret")
    with pytest.raises(ValidationFailed):
        storage.signed_url("../escape")
    with pytest.raises(ValidationFailed):
        storage.signed_url("/absolute")
