from django.db import models
from django.contrib.auth.models import User

class RoleChoices(models.TextChoices):
    ADMIN = 'ADMIN', 'Administrator'
    STAFF = 'STAFF', 'Staff'

class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    employee_id = models.CharField(max_length=64, unique=True, db_index=True)
    department = models.CharField(max_length=128, default='Faculty of Engineering & Computer Science')
    phone_number = models.CharField(max_length=32, blank=True)
    role = models.CharField(max_length=16, choices=RoleChoices.choices, default=RoleChoices.STAFF, db_index=True)
    assigned_block = models.CharField(max_length=128, default='Block B - Science & Tech Complex')
    notifications_enabled = models.BooleanField(default=True)
    alert_push_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'staff_profiles'
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.employee_id}) - {self.role}'

