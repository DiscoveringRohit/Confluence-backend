from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    """Define a model manager for User model with email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.GOV_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class University(models.Model):
    """Higher education institution participating in Confluence."""
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, blank=True)
    district = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.district})"


class Organization(models.Model):
    """Industry partner, startup, MSME, or CSR body."""
    name = models.CharField(max_length=255, unique=True)
    org_type = models.CharField(
        max_length=50,
        choices=[
            ('industry', 'Industry'),
            ('startup', 'Startup'),
            ('msme', 'MSME'),
            ('csr', 'CSR Partner')
        ],
        default='industry'
    )
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} [{self.get_org_type_display()}]"


class User(AbstractUser):
    """
    Role-scoped User model representing all 6 platform actors.
    """
    class Role(models.TextChoices):
        CITIZEN = 'citizen', 'Citizen / Community'
        STUDENT = 'student', 'Student'
        FACULTY_MENTOR = 'faculty_mentor', 'Faculty Mentor'
        UNIVERSITY_COORDINATOR = 'university_coordinator', 'University Coordinator'
        INDUSTRY_PARTNER = 'industry_partner', 'Industry Partner'
        GOV_ADMIN = 'gov_admin', 'Government Admin'

    username = None  # Use email as unique identifier
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.CITIZEN)
    
    # Institution links
    university = models.ForeignKey(
        University,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='affiliated_users',
        help_text="Set for student, faculty_mentor, and university_coordinator"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='affiliated_users',
        help_text="Set for industry_partner"
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.get_role_display()}"
