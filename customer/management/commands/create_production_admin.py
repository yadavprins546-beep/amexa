import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the AMEXA production superuser"

    def handle(self, *args, **options):
        email = os.environ.get("ADMIN_EMAIL", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        name = os.environ.get("ADMIN_NAME", "AMEXA Admin").strip()
        phone = os.environ.get("ADMIN_PHONE", "").strip()

        if not email:
            raise CommandError("ADMIN_EMAIL environment variable is missing.")

        if not password:
            raise CommandError("ADMIN_PASSWORD environment variable is missing.")

        User = get_user_model()

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "name": name,
                "phone": phone,
                "role": "ADMIN",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        user.name = name
        user.phone = phone
        user.role = "ADMIN"
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS("Production admin created successfully.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("Production admin updated successfully.")
            )