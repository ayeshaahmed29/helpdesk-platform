import io


def test_agent_can_upload_attachment(client, world, login_as):
    login_as(world.agent_a)
    file = io.BytesIO(b"hello world")
    response = client.post(
        f"/tickets/{world.ticket_a.id}/attachments",
        files={"file": ("test.txt", file, "text/plain")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["content_type"] == "text/plain"
    assert data["size"] == 11
    assert data["ticket_id"] == world.ticket_a.id


def test_customer_can_upload_to_own_ticket(client, world, login_as):
    login_as(world.customer_a)
    file = io.BytesIO(b"customer file")
    response = client.post(
        f"/tickets/{world.ticket_a.id}/attachments",
        files={"file": ("doc.txt", file, "text/plain")},
    )
    assert response.status_code == 201


def test_other_org_cannot_upload(client, world, login_as):
    login_as(world.agent_b)
    file = io.BytesIO(b"sneaky")
    response = client.post(
        f"/tickets/{world.ticket_a.id}/attachments",
        files={"file": ("hack.txt", file, "text/plain")},
    )
    assert response.status_code == 404


def test_oversized_file_rejected(client, world, login_as):
    login_as(world.agent_a)
    big_file = io.BytesIO(b"x" * (5 * 1024 * 1024 + 1))
    response = client.post(
        f"/tickets/{world.ticket_a.id}/attachments",
        files={"file": ("big.txt", big_file, "text/plain")},
    )
    assert response.status_code == 400
    assert "5 MB" in response.json()["detail"]


def test_disallowed_type_rejected(client, world, login_as):
    login_as(world.agent_a)
    file = io.BytesIO(b"not an exe")
    response = client.post(
        f"/tickets/{world.ticket_a.id}/attachments",
        files={"file": ("virus.exe", file, "application/x-msdownload")},
    )
    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


def test_list_attachments(client, world, login_as):
    login_as(world.agent_a)
    client.post(
        f"/tickets/{world.ticket_a.id}/attachments",
        files={"file": ("a.txt", io.BytesIO(b"aaa"), "text/plain")},
    )
    client.post(
        f"/tickets/{world.ticket_a.id}/attachments",
        files={"file": ("b.pdf", io.BytesIO(b"bbb"), "application/pdf")},
    )
    response = client.get(f"/tickets/{world.ticket_a.id}/attachments")
    assert response.status_code == 200
    assert len(response.json()) >= 2


def test_download_attachment(client, world, login_as):
    login_as(world.agent_a)
    upload = client.post(
        f"/tickets/{world.ticket_a.id}/attachments",
        files={"file": ("hello.txt", io.BytesIO(b"hello world"), "text/plain")},
    )
    att_id = upload.json()["id"]
    response = client.get(f"/attachments/{att_id}/download")
    assert response.status_code == 200
    assert response.content == b"hello world"


def test_other_org_cannot_download(client, world, login_as):
    login_as(world.agent_a)
    upload = client.post(
        f"/tickets/{world.ticket_a.id}/attachments",
        files={"file": ("secret.txt", io.BytesIO(b"secret"), "text/plain")},
    )
    att_id = upload.json()["id"]

    login_as(world.agent_b)
    response = client.get(f"/attachments/{att_id}/download")
    assert response.status_code == 404