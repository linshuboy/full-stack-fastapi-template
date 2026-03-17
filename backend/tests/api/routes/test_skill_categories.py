from fastapi.testclient import TestClient

from app.core.config import settings


def test_read_default_skill_categories(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/skill-categories/?include_inactive=true",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    names = {item["name"] for item in content["data"]}
    assert "文档处理" in names
    assert "知识库管理" in names
    assert "其他" in names


def test_create_update_delete_skill_category(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    create_data = {
        "name": "自动化测试",
        "description": "测试分类",
        "sort_order": 100,
        "is_active": True,
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/skill-categories/",
        headers=superuser_token_headers,
        json=create_data,
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == create_data["name"]
    category_id = created["id"]

    update_response = client.patch(
        f"{settings.API_V1_STR}/skill-categories/{category_id}",
        headers=superuser_token_headers,
        json={"description": "已更新", "is_active": False},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["description"] == "已更新"
    assert updated["is_active"] is False

    delete_response = client.delete(
        f"{settings.API_V1_STR}/skill-categories/{category_id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Category deleted successfully"


def test_create_skill_category_duplicate_name(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "name": "重复分类",
        "description": "a",
        "sort_order": 1,
        "is_active": True,
    }
    first = client.post(
        f"{settings.API_V1_STR}/skill-categories/",
        headers=superuser_token_headers,
        json=data,
    )
    assert first.status_code == 200

    second = client.post(
        f"{settings.API_V1_STR}/skill-categories/",
        headers=superuser_token_headers,
        json=data,
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Category name already exists"


def test_normal_user_cannot_manage_skill_categories(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/skill-categories/",
        headers=normal_user_token_headers,
        json={
            "name": "无权限分类",
            "description": "x",
            "sort_order": 1,
            "is_active": True,
        },
    )
    assert response.status_code == 403
