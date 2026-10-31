import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.accounts.models import StaffProfile, RoleChoices

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def staff_user(db):
    user = User.objects.create_user(
        username='prof_sharma',
        email='r.sharma@institution.edu',
        password='StrongPassword123!',
        first_name='Rahul',
        last_name='Sharma'
    )
    StaffProfile.objects.create(
        user=user,
        employee_id='FAC-ECE-2024-001',
        department='Department of Electrical & Electronics',
        role=RoleChoices.STAFF,
        assigned_block='Block B - Labs'
    )
    return user

@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username='admin_director',
        email='director@institution.edu',
        password='AdminMasterPassword123!',
        first_name='Vikram',
        last_name='Aditya',
        is_staff=True
    )
    StaffProfile.objects.create(
        user=user,
        employee_id='ADM-ENG-001',
        department='Campus Facilities & Management',
        role=RoleChoices.ADMIN,
        assigned_block='All Campus Buildings'
    )
    return user


@pytest.mark.django_db
class TestAuthenticationEndpoints:

    def test_login_success(self, api_client, staff_user):
        response = api_client.post('/api/v1/auth/login/', {
            'username': 'prof_sharma',
            'password': 'StrongPassword123!'
        }, format='json')

        assert response.status_code == 200
        data = response.data
        assert 'access' in data
        assert 'refresh' in data
        assert 'user' in data
        assert data['user']['username'] == 'prof_sharma'
        assert data['user']['role'] == 'STAFF'
        assert data['user']['employee_id'] == 'FAC-ECE-2024-001'

    def test_login_invalid_credentials(self, api_client, staff_user):
        response = api_client.post('/api/v1/auth/login/', {
            'username': 'prof_sharma',
            'password': 'WrongPassword999!'
        }, format='json')

        assert response.status_code == 401

    def test_token_refresh(self, api_client, staff_user):
        login_resp = api_client.post('/api/v1/auth/login/', {
            'username': 'prof_sharma',
            'password': 'StrongPassword123!'
        }, format='json')
        refresh_token = login_resp.data['refresh']

        refresh_resp = api_client.post('/api/v1/auth/token/refresh/', {
            'refresh': refresh_token
        }, format='json')

        assert refresh_resp.status_code == 200
        assert 'access' in refresh_resp.data

    def test_current_user_profile_me(self, api_client, staff_user):
        login_resp = api_client.post('/api/v1/auth/login/', {
            'username': 'prof_sharma',
            'password': 'StrongPassword123!'
        }, format='json')
        access_token = login_resp.data['access']

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_resp = api_client.get('/api/v1/auth/me/')

        assert profile_resp.status_code == 200
        assert profile_resp.data['username'] == 'prof_sharma'
        assert profile_resp.data['email'] == 'r.sharma@institution.edu'
        assert profile_resp.data['profile']['employee_id'] == 'FAC-ECE-2024-001'
        assert profile_resp.data['profile']['role'] == 'STAFF'

    def test_update_profile_preferences(self, api_client, staff_user):
        login_resp = api_client.post('/api/v1/auth/login/', {
            'username': 'prof_sharma',
            'password': 'StrongPassword123!'
        }, format='json')
        access_token = login_resp.data['access']

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        patch_resp = api_client.patch('/api/v1/auth/me/', {
            'profile': {
                'notifications_enabled': False,
                'phone_number': '+91-9876543210'
            }
        }, format='json')

        assert patch_resp.status_code == 200
        assert patch_resp.data['profile']['notifications_enabled'] is False
        assert patch_resp.data['profile']['phone_number'] == '+91-9876543210'

    def test_change_password_flow(self, api_client, staff_user):
        login_resp = api_client.post('/api/v1/auth/login/', {
            'username': 'prof_sharma',
            'password': 'StrongPassword123!'
        }, format='json')
        access_token = login_resp.data['access']

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        chg_resp = api_client.post('/api/v1/auth/change-password/', {
            'old_password': 'StrongPassword123!',
            'new_password': 'NewBrandPassword2026!#',
            'confirm_new_password': 'NewBrandPassword2026!#'
        }, format='json')

        assert chg_resp.status_code == 200

        # Verify old password no longer works
        api_client.credentials()  # clear auth header
        fail_login = api_client.post('/api/v1/auth/login/', {
            'username': 'prof_sharma',
            'password': 'StrongPassword123!'
        }, format='json')
        assert fail_login.status_code == 401

        # Verify new password works
        success_login = api_client.post('/api/v1/auth/login/', {
            'username': 'prof_sharma',
            'password': 'NewBrandPassword2026!#'
        }, format='json')
        assert success_login.status_code == 200

    def test_logout_and_token_blacklist(self, api_client, staff_user):
        login_resp = api_client.post('/api/v1/auth/login/', {
            'username': 'prof_sharma',
            'password': 'StrongPassword123!'
        }, format='json')
        access_token = login_resp.data['access']
        refresh_token = login_resp.data['refresh']

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_resp = api_client.post('/api/v1/auth/logout/', {
            'refresh': refresh_token
        }, format='json')

        assert logout_resp.status_code == 200

        # Attempting to refresh with blacklisted token should fail
        refresh_attempt = api_client.post('/api/v1/auth/token/refresh/', {
            'refresh': refresh_token
        }, format='json')
        assert refresh_attempt.status_code == 401

