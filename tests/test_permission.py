import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.mark.parametrize("role,expected_status", [
    ("user", 403),
    ("admin", 200),
])
def test_admin_route_access(role, expected_status):
    # 模拟不同角色访问管理员接口
    response = client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {role}_token"}
    )
    assert response.status_code == expected_status

def test_user_cannot_delete_others_data():
    # 普通用户尝试删除其他用户数据
    response = client.delete(
        "/api/users/123",
        headers={"Authorization": "Bearer user_token"}
    )
    assert response.status_code == 403
    assert "Permission denied" in response.json()["detail"]