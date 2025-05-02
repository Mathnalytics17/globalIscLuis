from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from apps.users.api.models.index import User, EmailVerificationToken, PasswordResetToken
from django.utils.safestring import mark_safe  # ¡Importación añadida!
class CustomUserAdmin(UserAdmin):
    # Campos a mostrar en la lista
    list_display = ('email', 'role', 'is_active', 'email_verified', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'email_verified')
    search_fields = ('email', 'phone')
    ordering = ('email',)  # Ordenar por email en lugar de username
    
    # Campos en el formulario de edición
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone', 'avatar', 'role')}),
        (_('Permissions'), {
            'fields': ('is_active', 'email_verified', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
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