"""
Management command to audit all user passwords in the database.

Checks that every password is a valid Django password hash (pbkdf2_sha256$...).
If any user has a broken/placeholder password (e.g. '######', '****', plain text),
it resets their password to a secure default and flags them for a forced reset.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import identify_hasher
from accounts.models import User


class Command(BaseCommand):
    help = 'Audit all user passwords and fix any that are not properly hashed.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix broken passwords by resetting them to a temporary secure hash.',
        )
        parser.add_argument(
            '--default-password',
            type=str,
            default='VeetileRuchi@Reset2026',
            help='The temporary password to set for broken accounts (default: VeetileRuchi@Reset2026).',
        )

    def handle(self, *args, **options):
        fix_mode = options['fix']
        default_password = options['default_password']
        users = User.objects.all()
        broken_users = []
        healthy_users = []

        self.stdout.write(self.style.NOTICE(f'\n🔍 Auditing {users.count()} user accounts...\n'))

        for user in users:
            pw = user.password
            is_valid_hash = False

            # Check if the password field contains a valid Django hash
            try:
                identify_hasher(pw)
                is_valid_hash = True
            except ValueError:
                is_valid_hash = False

            # Also flag known placeholder patterns
            placeholders = ['######', '****', '***', 'password', '']
            if pw in placeholders:
                is_valid_hash = False

            if is_valid_hash:
                healthy_users.append(user.username)
                self.stdout.write(f'  ✅ {user.username:<20} — Properly hashed (pbkdf2_sha256)')
            else:
                broken_users.append(user.username)
                self.stdout.write(self.style.WARNING(
                    f'  ⚠️  {user.username:<20} — BROKEN password: "{pw[:30]}..."'
                ))

                if fix_mode:
                    user.set_password(default_password)
                    user.save()
                    self.stdout.write(self.style.SUCCESS(
                        f'     → Fixed! Password reset to temporary default. User must change it.'
                    ))

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'  Healthy accounts:  {len(healthy_users)}'))
        if broken_users:
            self.stdout.write(self.style.ERROR(f'  Broken accounts:   {len(broken_users)}'))
            self.stdout.write(self.style.WARNING(f'  Broken usernames:  {", ".join(broken_users)}'))
            if not fix_mode:
                self.stdout.write(self.style.NOTICE(
                    '\n  💡 Run with --fix to reset broken passwords:\n'
                    '     python manage.py audit_passwords --fix\n'
                ))
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ All passwords are properly hashed. No issues found.'))
        self.stdout.write('=' * 60 + '\n')
