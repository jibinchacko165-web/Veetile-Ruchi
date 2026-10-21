import csv
import os
from django.core.management.base import BaseCommand
from delivery.models import District, HotelBranch

class Command(BaseCommand):
    help = 'Imports or updates Hotel / Kitchen branches from a validated CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to the CSV file containing branch details')
        parser.add_argument('--dry-run', action='store_true', help='Validate CSV without committing to database')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        dry_run = options['dry_run']

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            return

        self.stdout.write(f"Processing branch import from {csv_path} (dry-run: {dry_run})...")

        valid_count = 0
        skipped_count = 0
        errors = []

        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            required_fields = {'name', 'district', 'address', 'latitude', 'longitude'}
            
            if not required_fields.issubset(set(reader.fieldnames or [])):
                missing = required_fields - set(reader.fieldnames or [])
                self.stderr.write(self.style.ERROR(f"Missing required CSV columns: {missing}"))
                return

            for idx, row in enumerate(reader, start=2):
                name = (row.get('name') or '').strip()
                dist_name = (row.get('district') or '').strip()
                address = (row.get('address') or '').strip()
                raw_lat = (row.get('latitude') or '').strip()
                raw_lon = (row.get('longitude') or '').strip()
                raw_radius = (row.get('max_delivery_radius_km') or '25.0').strip()
                phone = (row.get('phone') or '').strip()
                status = (row.get('operating_status') or 'open').strip()

                if not name or not dist_name or not address:
                    errors.append(f"Row {idx}: Name, district, and address are required.")
                    skipped_count += 1
                    continue

                # Validate coordinates
                try:
                    lat = float(raw_lat)
                    lon = float(raw_lon)
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        raise ValueError("Out of bounds")
                except ValueError:
                    errors.append(f"Row {idx} ({name}): Invalid latitude/longitude ({raw_lat}, {raw_lon}).")
                    skipped_count += 1
                    continue

                # Validate radius (maximum 30 km strict limit)
                try:
                    radius = float(raw_radius)
                    if radius <= 0:
                        radius = 30.0
                    radius = min(radius, 30.0) # Strict ceiling of 30 km
                except ValueError:
                    radius = 30.0

                # Match district
                district = District.objects.filter(name__iexact=dist_name).first()
                if not district:
                    errors.append(f"Row {idx} ({name}): District '{dist_name}' does not match any of the 14 Kerala districts.")
                    skipped_count += 1
                    continue

                if not dry_run:
                    branch, created = HotelBranch.objects.update_or_create(
                        name=name,
                        district=district,
                        defaults={
                            'address': address,
                            'latitude': lat,
                            'longitude': lon,
                            'max_delivery_radius_km': radius,
                            'phone': phone,
                            'operating_status': status if status in ['open', 'busy', 'closed'] else 'open',
                            'is_active': True,
                        }
                    )
                    action = "Created" if created else "Updated"
                    self.stdout.write(f"  ✓ {action}: {branch.name} [{district.name}] (Radius: {branch.effective_radius_km} km)")
                else:
                    self.stdout.write(f"  ✓ Valid: {name} [{district.name}] at ({lat}, {lon}) (Radius: {radius} km)")

                valid_count += 1

        if errors:
            self.stdout.write(self.style.WARNING(f"\nEncountered {len(errors)} validation warnings:"))
            for err in errors:
                self.stdout.write(self.style.WARNING(f"  ! {err}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nImport finished! Valid: {valid_count}, Skipped: {skipped_count}"
        ))
