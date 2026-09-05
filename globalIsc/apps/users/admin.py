from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from apps.users.api.models.index import (
    EmailVerificationToken,
    PasswordResetToken,
    SecurityPermission,
    SecurityRole,
    SecurityRolePermission,
    User,
    UserAuditLog,
    UserCompanyProfile,
    UserInvitation,
)
from django.utils.safestring import mark_safe  # ¡Importación añadida!
class CustomUserAdmin(UserAdmin):
    # Campos a mostrar en la lista
    list_display = ('email', 'role', 'access_status', 'is_active', 'email_verified', 'is_staff')
    list_filter = ('role', 'access_status', 'is_staff', 'is_superuser', 'is_active', 'email_verified')
    search_fields = ('email', 'phone')
    ordering = ('email',)  # Ordenar por email en lugar de username
    
    # Campos en el formulario de edición
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone', 'avatar', 'role', 'empresa')}),
        (_('Permissions'), {
            'fields': ('is_active', 'email_verified', 'access_status', 'is_read_only', 'blocked_at', 'blocked_by', 'block_reason', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    # Campos al añadir nuevo usuario
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role'),
        }),
    )
    
    # Para mostrar el avatar en el admin
    readonly_fields = ('avatar_preview',)
    
    def avatar_preview(self, obj):
        if obj.avatar:
            return mark_safe(f'<img src="{obj.avatar.url}" width="100" />')
        return "-"
    avatar_preview.short_description = _('Avatar Preview')

# Registrar modelos
admin.site.register(User, CustomUserAdmin)

@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'expires_at', 'is_valid')
    readonly_fields = ('token', 'created_at')
    list_filter = ('created_at', 'expires_at')
    search_fields = ('user__email', 'token')

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'expires_at', 'is_valid')
    readonly_fields = ('token', 'created_at')
    list_filter = ('created_at', 'expires_at')
    search_fields = ('user__email', 'token')


@admin.register(SecurityPermission)
class SecurityPermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "module", "action", "active")
    list_filter = ("module", "active")
    search_fields = ("code", "module", "action", "description")


class SecurityRolePermissionInline(admin.TabularInline):
    model = SecurityRolePermission
    extra = 0
    autocomplete_fields = ("permission",)


@admin.register(SecurityRole)
class SecurityRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "scope", "active", "editable", "legacy_role")
    list_filter = ("scope", "active", "editable")
    search_fields = ("name", "code", "description")
    inlines = [SecurityRolePermissionInline]


@admin.register(UserCompanyProfile)
class UserCompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "empresa", "role", "status", "is_company_admin")
    list_filter = ("status", "is_company_admin", "empresa", "role")
    search_fields = ("user__email", "empresa__nombre")
    autocomplete_fields = ("user", "role")


@admin.register(UserInvitation)
class UserInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "empresa", "role", "status", "is_company_admin", "expires_at")
    list_filter = ("status", "is_company_admin", "empresa", "role")
    search_fields = ("email", "empresa__nombre", "token")
    readonly_fields = ("token", "created_at", "updated_at")
    autocomplete_fields = ("role", "user", "invited_by")


@admin.register(UserAuditLog)
class UserAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target_user", "empresa", "created_at")
    list_filter = ("module", "action", "empresa")
    search_fields = ("action", "detail", "actor__email", "target_user__email", "empresa__nombre")
    readonly_fields = ("created_at",)
