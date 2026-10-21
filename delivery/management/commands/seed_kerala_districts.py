import os
from django.core.management.base import BaseCommand
from delivery.models import District, HotelBranch, DeliverySetting
from food.models import FoodItem

KERALA_14_DISTRICTS = [
    {
        'name': 'Thiruvananthapuram',
        'code': 'thiruvananthapuram',
        'latitude': 8.5241,
        'longitude': 76.9366,
    },
    {
        'name': 'Kollam',
        'code': 'kollam',
        'latitude': 8.8932,
        'longitude': 76.6141,
    },
    {
        'name': 'Pathanamthitta',
        'code': 'pathanamthitta',
        'latitude': 9.2648,
        'longitude': 76.7870,
    },
    {
        'name': 'Alappuzha',
        'code': 'alappuzha',
        'latitude': 9.4981,
        'longitude': 76.3388,
    },
    {
        'name': 'Kottayam',
        'code': 'kottayam',
        'latitude': 9.5916,
        'longitude': 76.5222,
    },
    {
        'name': 'Idukki',
        'code': 'idukki',
        'latitude': 9.8500,
        'longitude': 76.9400,
    },
    {
        'name': 'Ernakulam',
        'code': 'ernakulam',
        'latitude': 9.9816,
        'longitude': 76.2999,
    },
    {
        'name': 'Thrissur',
        'code': 'thrissur',
        'latitude': 10.5276,
        'longitude': 76.2144,
    },
    {
        'name': 'Palakkad',
        'code': 'palakkad',
        'latitude': 10.7867,
        'longitude': 76.6548,
    },
    {
        'name': 'Malappuram',
        'code': 'malappuram',
        'latitude': 11.0735,
        'longitude': 76.0740,
    },
    {
        'name': 'Kozhikode',
        'code': 'kozhikode',
        'latitude': 11.2588,
        'longitude': 75.7804,
    },
    {
        'name': 'Wayanad',
        'code': 'wayanad',
        'latitude': 11.6103,
        'longitude': 76.0829,
    },
    {
        'name': 'Kannur',
        'code': 'kannur',
        'latitude': 11.8745,
        'longitude': 75.3704,
    },
    {
        'name': 'Kasaragod',
        'code': 'kasaragod',
        'latitude': 12.5102,
        'longitude': 74.9852,
    },
]

class Command(BaseCommand):
    help = 'Seeds all 14 Kerala districts and ensures Central Kitchen Hub is registered in Kottayam district.'

    def handle(self, *args, **options):
        self.stdout.write("Registering all 14 Kerala districts...")
        created_districts = 0
        updated_districts = 0

        for d_data in KERALA_14_DISTRICTS:
            district, created = District.objects.get_or_create(
                name=d_data['name'],
                defaults={
                    'code': d_data['code'],
                    'latitude': d_data['latitude'],
                    'longitude': d_data['longitude'],
                    'is_active': True,
                }
            )
            if created:
                created_districts += 1
            else:
                district.code = d_data['code']
                district.latitude = d_data['latitude']
                district.longitude = d_data['longitude']
                district.is_active = True
                district.save()
                updated_districts += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully verified all 14 districts! (Created: {created_districts}, Updated: {updated_districts})"
        ))

        # Register / Link Central Kitchen Hub in Kottayam
        kottayam = District.objects.get(name='Kottayam')
        setting = DeliverySetting.get_settings()

        central_hub, hub_created = HotelBranch.objects.get_or_create(
            is_central_hub=True,
            defaults={
                'name': setting.name or 'Central Kitchen Hub (Kanjirappally)',
                'district': kottayam,
                'address': setting.address or 'Kanjirappally Town, Kottayam, Kerala',
                'latitude': setting.latitude or 9.5564,
                'longitude': setting.longitude or 76.7909,
                'max_delivery_radius_km': 30.0,
                'is_active': True,
                'is_central_hub': True,
                'phone': '+91 7510672355',
                'opening_time': '07:00:00',
                'closing_time': '22:00:00',
                'operating_status': 'open',
            }
        )

        if not hub_created:
            central_hub.name = setting.name or 'Central Kitchen Hub (Kanjirappally)'
            central_hub.district = kottayam
            central_hub.address = setting.address or 'Kanjirappally Town, Kottayam, Kerala'
            central_hub.latitude = setting.latitude or 9.5564
            central_hub.longitude = setting.longitude or 76.7909
            central_hub.max_delivery_radius_km = 30.0
            central_hub.is_active = True
            central_hub.save()

        # Deactivate obsolete kitchen branches so Kanjirappally is the only active kitchen
        HotelBranch.objects.exclude(id=central_hub.id).update(is_active=False)

        # Link DeliverySetting to central hub
        setting.branch = central_hub
        setting.max_delivery_radius_km = 30.0
        setting.save()

        self.stdout.write(self.style.SUCCESS(
            f"Central Kitchen Hub verified: {central_hub.name} in {central_hub.district.name} ({central_hub.latitude}, {central_hub.longitude}) [Radius: {central_hub.effective_radius_km} km]"
        ))
