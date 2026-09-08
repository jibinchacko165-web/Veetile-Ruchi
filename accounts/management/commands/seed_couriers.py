from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import DeliveryBoyProfile

User = get_user_model()

COURIER_LIST = [
    {"phone": "7510672352", "username": "courier1", "first_name": "Courier", "last_name": "1", "vehicle": "KL-34-A-1001"},
    {"phone": "7510672351", "username": "courier2", "first_name": "Courier", "last_name": "2", "vehicle": "KL-34-A-1002"},
    {"phone": "7510672353", "username": "courier3", "first_name": "Courier", "last_name": "3", "vehicle": "KL-34-A-1003"},
    {"phone": "7510672354", "username": "courier4", "first_name": "Courier", "last_name": "4", "vehicle": "KL-34-A-1004"},
    {"phone": "7510672355", "username": "courier5", "first_name": "Courier", "last_name": "5", "vehicle": "KL-34-A-1005"},
    {"phone": "7510672355", "username": "courier",  "first_name": "Courier", "last_name": "5", "vehicle": "KL-34-A-1005"},
    {"phone": "7510672356", "username": "courier6", "first_name": "Courier", "last_name": "6", "vehicle": "KL-34-A-1006"},
    {"phone": "7510672357", "username": "courier7", "first_name": "Courier", "last_name": "7", "vehicle": "KL-34-A-1007"},
    {"phone": "7510672358", "username": "courier8", "first_name": "Courier", "last_name": "8", "vehicle": "KL-34-A-1008"},
    {"phone": "7510672359", "username": "courier9", "first_name": "Courier", "last_name": "9", "vehicle": "KL-34-A-1009"},
]

class Command(BaseCommand):
    help = 'Seed exactly 9 courier records with required phone numbers'

    def handle(self, *args, **kwargs):
        created_count = 0
        updated_count = 0
        
        for info in COURIER_LIST:
            phone = info["phone"]
            username = info["username"]
            
            user = User.objects.filter(username=username).first()
            
            if not user:
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@ruchi.com",
                    password="password123",
                    role="delivery_boy",
                    phone=phone,
                    first_name=info["first_name"],
                    last_name=info["last_name"],
                    is_active=True
                )
                created_count += 1
            else:
                user.username = username
                user.role = "delivery_boy"
                user.phone = phone
                user.first_name = info["first_name"]
                user.last_name = info["last_name"]
                user.set_password("password123")
                user.is_active = True
                user.save()
                updated_count += 1

            profile, _ = DeliveryBoyProfile.objects.get_or_create(user=user)
            profile.vehicle_number = info["vehicle"]
            if profile.status not in ['available', 'on_delivery', 'busy', 'offline']:
                profile.status = 'available'
            profile.save()

        self.stdout.write(self.style.SUCCESS(f"Successfully configured 9 courier records! (Created: {created_count}, Updated: {updated_count})"))
