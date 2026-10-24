from django.core.management.base import BaseCommand
import sys
import os

from scratch.seed_24_kerala_foods import run_seed

class Command(BaseCommand):
    help = 'Seeds the 24 authentic Kerala foods, images, meal schedules, and nutritional metadata.'

    def handle(self, *args, **options):
        run_seed()
        self.stdout.write(self.style.SUCCESS("Successfully seeded 24 authentic Kerala food items!"))
