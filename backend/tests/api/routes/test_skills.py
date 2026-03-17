import tarfile
import zipfile
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings

ARCHIVE_RULE_DETAIL = (
    "Archive must contain exactly one top-level directory and exactly one "
    "SKILL.md file (case-insensitive)"
)


def _get_active_category_id(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> str:
    response = client.get(
        f"{settings.API_V1_STR}/skill-categories/?include_inactive=true",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    categories = response.json()["data"]
    assert len(categories) > 0
    return categories[0]["id"]


def _build_zip_archive(files: dict[str, bytes], root_dir: str = "demo-skill") -> bytes:
    archive_bytes = BytesIO()
    with zipfile.ZipFile(archive_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_name, content in files.items():
            archive_path = f"{root_dir}/{file_name}" if root_dir else file_name
            zf.writestr(archive_path, content)
    return archive_bytes.getvalue()


def _build_tar_archive(
    files: dict[str, bytes], mode: str = "w", root_dir: str = "demo-skill"
) -> bytes:
    archive_bytes = BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode=mode) as tf:
        for file_name, content in files.items():
            archive_path = f"{root_dir}/{file_name}" if root_dir else file_name
            info = tarfile.TarInfo(name=archive_path)
            info.size = len(content)
            tf.addfile(info, BytesIO(content))
    return archive_bytes.getvalue()


def test_create_skill_with_archive(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    archive_bytes = _build_zip_archive({"SKILL.md": b"# demo skill"})
    with patch("app.api.routes.skills.upload_skill_file", return_value=None):
        response = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "示例技能",
                "description": "一个技能包",
                "category_id": category_id,
                "is_published": "true",
            },
            files={"file": ("demo.zip", archive_bytes, "application/zip")},
        )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == "示例技能"
    assert content["category_id"] == category_id
    assert content["file_name"] == "demo.zip"
    assert content["archive_root_dir"] == "demo-skill"
    assert content["is_published"] is True


def test_create_skill_invalid_archive_extension(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/skills/",
        headers=superuser_token_headers,
        data={
            "title": "非法文件",
            "description": "bad",
            "category_id": category_id,
            "is_published": "true",
        },
        files={"file": ("demo.txt", b"text-content", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only .zip, .tar, .tar.gz, .tgz files are supported"


def test_create_skill_requires_single_top_level_dir_and_skill_md(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    archive_bytes = _build_zip_archive({"metadata.json": b"{}"})
    response = client.post(
        f"{settings.API_V1_STR}/skills/",
        headers=superuser_token_headers,
        data={
            "title": "缺少 skill.md",
            "description": "bad",
            "category_id": category_id,
            "is_published": "true",
        },
        files={"file": ("missing-skill.zip", archive_bytes, "application/zip")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == ARCHIVE_RULE_DETAIL


def test_create_skill_requires_single_top_level_directory_only(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    archive_bytes = _build_zip_archive(
        {
            "pkg-a/SKILL.md": b"# a",
            "pkg-b/metadata.json": b"{}",
        },
        root_dir="",
    )
    response = client.post(
        f"{settings.API_V1_STR}/skills/",
        headers=superuser_token_headers,
        data={
            "title": "多一级目录",
            "description": "bad",
            "category_id": category_id,
            "is_published": "true",
        },
        files={"file": ("multiple-top-level.zip", archive_bytes, "application/zip")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == ARCHIVE_RULE_DETAIL


def test_create_skill_rejects_duplicate_file_name(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    first_archive = _build_zip_archive({"SKILL.md": b"# first"})
    second_archive = _build_zip_archive({"SKILL.md": b"# second"})

    with patch("app.api.routes.skills.upload_skill_file", return_value=None):
        first_response = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "重复文件名1",
                "description": "dup 1",
                "category_id": category_id,
                "is_published": "true",
            },
            files={"file": ("duplicate.zip", first_archive, "application/zip")},
        )
    assert first_response.status_code == 200

    second_response = client.post(
        f"{settings.API_V1_STR}/skills/",
        headers=superuser_token_headers,
        data={
            "title": "重复文件名2",
            "description": "dup 2",
            "category_id": category_id,
            "is_published": "true",
        },
        files={"file": ("DUPLICATE.zip", second_archive, "application/zip")},
    )
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Archive file name already exists"


def test_read_skills_for_normal_user_only_published(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    pub_archive = _build_tar_archive({"SKILL.md": b"# public"})
    hidden_archive = _build_zip_archive({"skill.md": b"# hidden"})
    with patch("app.api.routes.skills.upload_skill_file", return_value=None):
        pub = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "公开技能",
                "description": "pub",
                "category_id": category_id,
                "is_published": "true",
            },
            files={"file": ("pub.tar", pub_archive, "application/x-tar")},
        )
        hidden = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "私有技能",
                "description": "private",
                "category_id": category_id,
                "is_published": "false",
            },
            files={"file": ("hidden.zip", hidden_archive, "application/zip")},
        )
    assert pub.status_code == 200
    assert hidden.status_code == 200
    hidden_id = hidden.json()["id"]

    normal_list = client.get(
        f"{settings.API_V1_STR}/skills/?only_published=false",
        headers=normal_user_token_headers,
    )
    assert normal_list.status_code == 200
    skills = normal_list.json()["data"]
    assert all(skill["is_published"] for skill in skills)
    assert hidden_id not in [skill["id"] for skill in skills]


def test_update_skill_publish_and_download_url(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    archive_bytes = _build_tar_archive({"skill.md": b"# tgz"}, mode="w:gz")
    with patch("app.api.routes.skills.upload_skill_file", return_value=None):
        create_response = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "下载技能",
                "description": "download",
                "category_id": category_id,
                "is_published": "false",
            },
            files={"file": ("download.tgz", archive_bytes, "application/gzip")},
        )
    assert create_response.status_code == 200
    skill_id = create_response.json()["id"]

    publish_response = client.patch(
        f"{settings.API_V1_STR}/skills/{skill_id}/publish",
        headers=superuser_token_headers,
        json={"is_published": True},
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["is_published"] is True

    with patch(
        "app.api.routes.skills.get_skill_download_url",
        return_value=(
            "http://minio:9000/skills/demo-object?"
            "X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=demo"
        ),
    ):
        download_response = client.get(
            f"{settings.API_V1_STR}/skills/{skill_id}/download",
            headers=superuser_token_headers,
        )
    assert download_response.status_code == 200
    assert download_response.json()["url"].startswith(
        "http://testserver/minio/skills/demo-object?"
    )


def test_get_install_url(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    archive_bytes = _build_zip_archive({"SKILL.md": b"# install"})
    with patch("app.api.routes.skills.upload_skill_file", return_value=None):
        create_response = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "安装地址技能",
                "description": "install",
                "category_id": category_id,
                "is_published": "true",
            },
            files={"file": ("install.zip", archive_bytes, "application/zip")},
        )
    assert create_response.status_code == 200
    skill_id = create_response.json()["id"]

    with patch(
        "app.api.routes.skills.get_skill_download_url",
        return_value=(
            "http://minio:9000/skills/install-object?"
            "X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=install"
        ),
    ):
        install_response = client.get(
            f"{settings.API_V1_STR}/skills/{skill_id}/install-url",
            headers=superuser_token_headers,
        )
    assert install_response.status_code == 200
    assert install_response.json()["url"].startswith(
        "http://testserver/minio/skills/install-object?"
    )


def test_delete_skill_and_block_category_deletion_when_in_use(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_response = client.post(
        f"{settings.API_V1_STR}/skill-categories/",
        headers=superuser_token_headers,
        json={
            "name": "删除测试分类",
            "description": "for delete test",
            "sort_order": 999,
            "is_active": True,
        },
    )
    assert category_response.status_code == 200
    category_id = category_response.json()["id"]
    archive_bytes = _build_zip_archive({"SKILL.md": b"# to delete"})

    with patch("app.api.routes.skills.upload_skill_file", return_value=None):
        create_response = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "删除测试技能",
                "description": "x",
                "category_id": category_id,
                "is_published": "true",
            },
            files={"file": ("to-delete.zip", archive_bytes, "application/zip")},
        )
    assert create_response.status_code == 200
    skill_id = create_response.json()["id"]

    blocked_delete_category = client.delete(
        f"{settings.API_V1_STR}/skill-categories/{category_id}",
        headers=superuser_token_headers,
    )
    assert blocked_delete_category.status_code == 400
    assert (
        blocked_delete_category.json()["detail"]
        == "Cannot delete category with existing skills"
    )

    with patch("app.api.routes.skills.delete_skill_file", return_value=None):
        delete_skill_response = client.delete(
            f"{settings.API_V1_STR}/skills/{skill_id}",
            headers=superuser_token_headers,
        )
    assert delete_skill_response.status_code == 200
    assert delete_skill_response.json()["message"] == "Skill deleted successfully"


def test_replace_skill_file_requires_single_top_level_dir_and_skill_md(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    valid_archive = _build_zip_archive({"SKILL.md": b"# ok"})
    with patch("app.api.routes.skills.upload_skill_file", return_value=None):
        create_response = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "替换测试技能",
                "description": "replace test",
                "category_id": category_id,
                "is_published": "true",
            },
            files={"file": ("replace-source.zip", valid_archive, "application/zip")},
        )
    assert create_response.status_code == 200
    skill_id = create_response.json()["id"]

    invalid_archive = _build_zip_archive({"metadata.json": b"{}"})
    with patch("app.api.routes.skills.upload_skill_file", return_value=None) as mocked:
        replace_response = client.post(
            f"{settings.API_V1_STR}/skills/{skill_id}/file",
            headers=superuser_token_headers,
            files={"file": ("replace-target.zip", invalid_archive, "application/zip")},
        )
    assert replace_response.status_code == 400
    assert replace_response.json()["detail"] == ARCHIVE_RULE_DETAIL
    mocked.assert_not_called()


def test_replace_skill_file_rejects_duplicate_file_name(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    source_archive = _build_zip_archive({"SKILL.md": b"# source"})
    target_archive = _build_zip_archive({"SKILL.md": b"# target"})

    with patch("app.api.routes.skills.upload_skill_file", return_value=None):
        first_response = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "技能A",
                "description": "a",
                "category_id": category_id,
                "is_published": "true",
            },
            files={"file": ("alpha.zip", source_archive, "application/zip")},
        )
        second_response = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "技能B",
                "description": "b",
                "category_id": category_id,
                "is_published": "true",
            },
            files={"file": ("beta.zip", target_archive, "application/zip")},
        )
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    second_skill_id = second_response.json()["id"]
    replace_archive = _build_zip_archive({"SKILL.md": b"# replacement"}, root_dir="other-skill")
    replace_response = client.post(
        f"{settings.API_V1_STR}/skills/{second_skill_id}/file",
        headers=superuser_token_headers,
        files={"file": ("ALPHA.zip", replace_archive, "application/zip")},
    )
    assert replace_response.status_code == 409
    assert replace_response.json()["detail"] == "Archive file name already exists"


def test_replace_skill_file_updates_archive_root_dir(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category_id = _get_active_category_id(client, superuser_token_headers)
    source_archive = _build_zip_archive({"SKILL.md": b"# source"}, root_dir="pkg-a")
    with patch("app.api.routes.skills.upload_skill_file", return_value=None):
        create_response = client.post(
            f"{settings.API_V1_STR}/skills/",
            headers=superuser_token_headers,
            data={
                "title": "根目录更新测试",
                "description": "root dir update",
                "category_id": category_id,
                "is_published": "true",
            },
            files={"file": ("root-dir-update.zip", source_archive, "application/zip")},
        )
    assert create_response.status_code == 200
    skill_id = create_response.json()["id"]
    assert create_response.json()["archive_root_dir"] == "pkg-a"

    replacement_archive = _build_zip_archive({"SKILL.md": b"# replacement"}, root_dir="pkg-b")
    with patch("app.api.routes.skills.upload_skill_file", return_value=None), patch(
        "app.api.routes.skills.delete_skill_file", return_value=None
    ):
        replace_response = client.post(
            f"{settings.API_V1_STR}/skills/{skill_id}/file",
            headers=superuser_token_headers,
            files={
                "file": (
                    "root-dir-update-replaced.zip",
                    replacement_archive,
                    "application/zip",
                )
            },
        )
    assert replace_response.status_code == 200
    assert replace_response.json()["archive_root_dir"] == "pkg-b"
