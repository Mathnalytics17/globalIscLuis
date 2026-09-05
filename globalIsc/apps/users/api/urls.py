from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views.security import (
    SecurityPermissionViewSet,
    SecurityRoleViewSet,
    UserAuditLogViewSet,
    UserCompanyProfileViewSet,
    UserInvitationViewSet,
    UserSecurityViewSet,
)
from .views.user.index import (
    CurrentUserView,
    EmailVerificationView,
    ForgotPasswordView,
    LoginAV,
    PasswordResetConfirmView,
    UserDetailView,
    UserRegistrationView,
    UserViewSet,
)


urlpatterns = [
    path("users/", UserViewSet.as_view({"get": "list"}), name="user-list"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("users/register/", UserRegistrationView.as_view(), name="register"),
    path("users/login/", LoginAV.as_view(), name="token_obtain_pair"),
    path("users/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("users/verify-email/", EmailVerificationView.as_view(), name="verify_email"),
    path("users/password-reset/", ForgotPasswordView.as_view(), name="password_reset"),
    path("users/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("users/me/", CurrentUserView.as_view(), name="current-user"),
    path("security/permissions/", SecurityPermissionViewSet.as_view({"get": "list"}), name="security-permissions-list"),
    path("security/permissions/seed-defaults/", SecurityPermissionViewSet.as_view({"post": "seed_defaults"}), name="security-permissions-seed-defaults"),
    path("security/roles/", SecurityRoleViewSet.as_view({"get": "list", "post": "create"}), name="security-roles-list"),
    path("security/roles/assignable/", SecurityRoleViewSet.as_view({"get": "assignable"}), name="security-roles-assignable"),
    path("security/roles/matrix/", SecurityRoleViewSet.as_view({"get": "matrix"}), name="security-roles-matrix"),
    path("security/roles/<int:pk>/", SecurityRoleViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="security-roles-detail"),
    path("security/roles/<int:pk>/matrix/", SecurityRoleViewSet.as_view({"put": "update_matrix", "patch": "update_matrix"}), name="security-roles-update-matrix"),
    path("security/roles/<int:pk>/reactivate/", SecurityRoleViewSet.as_view({"post": "reactivate"}), name="security-roles-reactivate"),
    path("security/user-profiles/", UserCompanyProfileViewSet.as_view({"get": "list", "post": "create"}), name="security-user-profiles-list"),
    path("security/user-profiles/<int:pk>/", UserCompanyProfileViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="security-user-profiles-detail"),
    path("security/invitations/", UserInvitationViewSet.as_view({"get": "list", "post": "create"}), name="security-invitations-list"),
    path("security/invitations/accept/", UserInvitationViewSet.as_view({"post": "accept"}), name="security-invitations-accept"),
    path("security/invitations/validate/", UserInvitationViewSet.as_view({"get": "validate_invitation"}), name="security-invitations-validate"),
    path("security/invitations/<int:pk>/", UserInvitationViewSet.as_view({"get": "retrieve", "delete": "destroy"}), name="security-invitations-detail"),
    path("security/invitations/<int:pk>/resend/", UserInvitationViewSet.as_view({"post": "resend"}), name="security-invitations-resend"),
    path("security/invitations/<int:pk>/revoke/", UserInvitationViewSet.as_view({"post": "revoke"}), name="security-invitations-revoke"),
    path("security/users/<int:pk>/block/", UserSecurityViewSet.as_view({"post": "block"}), name="security-users-block"),
    path("security/users/<int:pk>/unblock/", UserSecurityViewSet.as_view({"post": "unblock"}), name="security-users-unblock"),
    path("security/users/<int:pk>/read-only/", UserSecurityViewSet.as_view({"post": "read_only"}), name="security-users-read-only"),
    path("security/users/<int:pk>/restore-write/", UserSecurityViewSet.as_view({"post": "restore_write"}), name="security-users-restore-write"),
    path("security/users/<int:pk>/deactivate/", UserSecurityViewSet.as_view({"post": "deactivate"}), name="security-users-deactivate"),
    path("security/users/<int:pk>/reactivate/", UserSecurityViewSet.as_view({"post": "reactivate"}), name="security-users-reactivate"),
    path("security/users/<int:pk>/reinvite/", UserSecurityViewSet.as_view({"post": "reinvite"}), name="security-users-reinvite"),
    path("security/audit-logs/", UserAuditLogViewSet.as_view({"get": "list"}), name="security-audit-logs-list"),
]
