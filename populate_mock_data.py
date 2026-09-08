import os
import django
import datetime

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'veetile_ruchi_project.settings')
django.setup()

from django.utils import timezone
from accounts.models import User, ChefProfile, DeliveryBoyProfile
from food.models import Category, MealSession, FoodItem, NutritionInfo, ReviewSentiment
from orders.models import Coupon, Order, OrderItem, Payment
from delivery.models import DeliveryAssignment, GPSLocationTracking
from health.models import HealthProfile, HealthRecommendation
from ai_models.models import FoodDemandForecast, FoodWastePrediction, StockPrediction, CustomerBehavior

def seed_database():
    print("Starting database seeding...")
    
    # 1. Clear existing data to avoid duplicates
    GPSLocationTracking.objects.all().delete()
    DeliveryAssignment.objects.all().delete()
    Payment.objects.all().delete()
    OrderItem.objects.all().delete()
    Order.objects.all().delete()
    CartItem = django.apps.apps.get_model('orders', 'CartItem')
    CartItem.objects.all().delete()
    Wishlist = django.apps.apps.get_model('orders', 'Wishlist')
    Wishlist.objects.all().delete()
    Coupon.objects.all().delete()
    
    CustomerBehavior.objects.all().delete()
    StockPrediction.objects.all().delete()
    FoodWastePrediction.objects.all().delete()
    FoodDemandForecast.objects.all().delete()
    HealthRecommendation.objects.all().delete()
    HealthProfile.objects.all().delete()
    
    ReviewSentiment.objects.all().delete()
    NutritionInfo.objects.all().delete()
    FoodItem.objects.all().delete()
    MealSession.objects.all().delete()
    Category.objects.all().delete()
    
    User.objects.all().delete()

    # 2. Create Users
    admin = User.objects.create_user(username='admin', email='admin@ruchi.com', password='password123', role='admin', is_staff=True, is_superuser=True, dob='1990-01-01')
    staff = User.objects.create_user(username='staff', email='staff@ruchi.com', password='password123', role='staff', is_staff=True, dob='1992-03-10')
    
    chef_user = User.objects.create_user(username='chef', email='chef@ruchi.com', password='password123', role='chef', dob='1988-07-20')
    chef_profile = ChefProfile.objects.create(user=chef_user, specialty='Traditional Kerala Cuisine', is_approved=True)
    
    # Create exactly 9 distinct courier profiles with exact requested phone numbers
    courier_data = [
        {"phone": "7510672351", "username": "courier", "first_name": "Arun", "last_name": "Kumar", "vehicle": "KL-34-A-1001"},
        {"phone": "7510672352", "username": "courier2", "first_name": "Biju", "last_name": "Varghese", "vehicle": "KL-34-A-1002"},
        {"phone": "7510672353", "username": "courier3", "first_name": "Suresh", "last_name": "Nair", "vehicle": "KL-34-A-1003"},
        {"phone": "7510672354", "username": "courier4", "first_name": "Rahul", "last_name": "K", "vehicle": "KL-34-A-1004"},
        {"phone": "7510672355", "username": "courier5", "first_name": "Vipin", "last_name": "Das", "vehicle": "KL-34-A-1005"},
        {"phone": "7510672356", "username": "courier6", "first_name": "Anand", "last_name": "M", "vehicle": "KL-34-A-1006"},
        {"phone": "7510672357", "username": "courier7", "first_name": "Jithin", "last_name": "Paul", "vehicle": "KL-34-A-1007"},
        {"phone": "7510672358", "username": "courier8", "first_name": "Akhil", "last_name": "R", "vehicle": "KL-34-A-1008"},
        {"phone": "7510672359", "username": "courier9", "first_name": "Faisal", "last_name": "Khan", "vehicle": "KL-34-A-1009"},
    ]
    couriers = []
    for c_info in courier_data:
        u = User.objects.create_user(
            username=c_info["username"],
            first_name=c_info["first_name"],
            last_name=c_info["last_name"],
            email=f'{c_info["username"]}@ruchi.com',
            password='password123',
            role='delivery_boy',
            phone=c_info["phone"],
            dob='1996-08-12'
        )
        p = DeliveryBoyProfile.objects.create(user=u, vehicle_number=c_info["vehicle"], status='available')
        couriers.append(p)
    courier_profile = couriers[0]
    
    cust_user = User.objects.create_user(username='customer', first_name='Riya', last_name='P', email='customer@ruchi.com', password='password123', role='customer', phone='9876543210', dob='1995-05-15')
    cust_profile = HealthProfile.objects.create(user=cust_user, has_diabetes=True, dietary_preference='veg')

    # Also create username 'riya' with password 'riya123' to support direct login as Riya / riya123
    riya_user = User.objects.create_user(username='riya', first_name='Riya', last_name='P', email='riya@ruchi.com', password='riya123', role='customer', phone='9876543219', dob='1995-05-15')
    HealthProfile.objects.create(user=riya_user, has_diabetes=False, dietary_preference='veg')

    # 3. Create Categories
    print("Creating food categories...")
    veg = Category.objects.create(name='Vegetarian', description='Fresh vegetarian homemade dishes', image='/static/images/veg.jpg')
    non_veg = Category.objects.create(name='Non-Vegetarian', description='Delicious home-cooked meat and fish recipes', image='/static/images/nonveg.jpg')
    dessert = Category.objects.create(name='Desserts', description='Healthy sweets and traditional puddings', image='/static/images/desserts.jpg')

    # 4. Create Meal Sessions with exact requested time slots
    print("Creating meal sessions with exact requested time slots...")
    breakfast = MealSession.objects.create(name='Morning Breakfast', start_time='06:00:00', end_time='12:00:00')
    lunch = MealSession.objects.create(name='Lunch', start_time='12:00:00', end_time='16:00:00')
    snack = MealSession.objects.create(name='Evening Snacks', start_time='16:00:00', end_time='19:00:00')
    dinner = MealSession.objects.create(name='Dinner', start_time='19:00:00', end_time='23:59:59')

    # 5. Create 55 Authentic Kerala Food Items & Nutrition Specs
    print("Creating 55 authentic homemade Kerala food items...")
    
    foods_data = [
        # BREAKFAST (16 items)
        ("Puttu and Kadala Curry", 70.00, veg, breakfast, "/media/food_photos/puttu_and_kadala_curry.jpg", "Steamed rice flour puttu cylinders layered with coconut, served with spicy black chickpea curry.", 310.0, 1.5, 0.0, 110.0, 9.0, 4.0, 58.0, 7.0),
        ("Appam with Vegetable Stew", 85.00, veg, breakfast, "/media/food_photos/appam_with_vegetable_stew.jpg", "Lacy soft coconut rice pancakes served with mild creamy coconut milk vegetable stew.", 270.0, 2.0, 0.0, 95.0, 4.5, 6.5, 48.0, 3.5),
        ("Appam with Chicken Curry", 140.00, non_veg, breakfast, "/media/food_photos/appam_with_chicken_curry.jpg", "Soft fermented rice hoppers served with tender chicken cooked in spicy Kerala coconut curry.", 420.0, 2.5, 65.0, 310.0, 22.0, 16.0, 44.0, 2.0),
        ("Idiyappam with Egg Curry", 90.00, non_veg, breakfast, "/media/food_photos/idiyappam_with_egg_curry.jpg", "Soft steamed string hoppers accompanied by caramelised onion spiced egg roast gravy.", 340.0, 3.0, 185.0, 280.0, 12.0, 10.0, 50.0, 2.5),
        ("Idli with Sambar", 60.00, veg, breakfast, "/media/food_photos/idli_with_sambar.jpg", "Soft fluffy steamed rice cakes served with authentic Kerala vegetable sambar and coconut chutney.", 210.0, 1.0, 0.0, 140.0, 5.0, 2.0, 42.0, 3.0),
        ("Dosa with Sambar and Chutney", 65.00, veg, breakfast, "/media/food_photos/dosa_with_sambar_and_chutney.jpg", "Golden crispy rice-lentil crepe served with authentic Kerala vegetable sambar and fresh coconut chutney.", 240.0, 1.2, 0.0, 150.0, 5.5, 4.0, 45.0, 3.0),
        ("Kerala Parotta with Egg Curry", 85.00, non_veg, breakfast, "/media/food_photos/kerala_parotta_with_egg_curry.jpg", "Flaky layered golden parotta served with spicy caramelized onion egg roast curry.", 380.0, 2.0, 185.0, 310.0, 13.0, 15.0, 48.0, 2.0),
        ("Vellayappam with Chicken Curry", 135.00, non_veg, breakfast, "/media/food_photos/vellayappam_with_chicken_curry.jpg", "Soft fluffy white fermented rice hoppers served with authentic Nadan spicy Kerala chicken curry.", 410.0, 2.2, 60.0, 300.0, 21.0, 15.0, 45.0, 2.0),
        ("Kallappam with Egg Curry", 95.00, non_veg, breakfast, "/media/food_photos/kallappam_with_egg_curry.jpg", "Thick traditional coconut rice pancakes infused with cumin, served with rich onion egg curry.", 350.0, 2.5, 185.0, 290.0, 12.5, 11.0, 49.0, 2.5),
        ("Upma with Banana", 55.00, veg, breakfast, "/media/food_photos/upma_with_banana.jpg", "Roasted semolina cooked with mustard seeds, ginger, curry leaves, and fresh coconut, served with a ripe small banana.", 240.0, 10.0, 0.0, 110.0, 5.0, 4.5, 44.0, 3.5),
        ("Pazham Pori with Tea", 50.00, veg, breakfast, "/media/food_photos/pazham_pori_with_tea.jpg", "Crispy golden fried ripe banana fritters served with piping hot Kerala cardamom tea.", 230.0, 15.0, 0.0, 40.0, 3.0, 6.5, 40.0, 3.0),
        ("Neyyappam", 55.00, dessert, breakfast, "/media/food_photos/neyyappam_snack.jpg", "Traditional deep-fried sweet rice flour & jaggery fritters cooked in pure ghee.", 260.0, 18.0, 12.0, 35.0, 3.5, 8.0, 43.0, 2.0),
        ("Unniyappam", 50.00, dessert, breakfast, "/media/food_photos/unniyappam_snack.jpg", "Small round sweet rice fritters made with jaggery, banana, and roasted coconut bits.", 250.0, 18.0, 0.0, 30.0, 3.0, 7.0, 44.0, 2.0),
        ("Mutta Appam", 95.00, non_veg, breakfast, "/media/food_photos/mutta_appam.jpg", "Soft white lacy appam with a whole cooked egg poached in the fluffy center.", 320.0, 1.5, 185.0, 250.0, 14.0, 9.0, 42.0, 1.8),
        ("Kanji and Payar", 75.00, veg, breakfast, "/media/food_photos/Nadan Matta Rice Kanji & Payar.png", "Soothing warm Matta rice porridge served with green gram thoran, papad, and pickle.", 250.0, 0.5, 0.0, 120.0, 7.5, 1.5, 52.0, 5.0),
        ("Ragi Dosa with Coconut Chutney", 70.00, veg, breakfast, "/media/food_photos/Crispy Thattu Dosa & Coconut Chutney.png", "Nutritious finger millet (Ragi) steamed dosa served with mild coconut chutney.", 210.0, 0.8, 0.0, 90.0, 6.0, 2.5, 42.0, 6.5),

        # LUNCH (16 items)
        ("Kerala Sadya", 240.00, veg, lunch, "/media/food_photos/Kerala Traditional Sadya Feast.png", "Grand festival feast served on banana leaf with Matta rice, Parippu, Ghee, Avial, Thoran, Sambar, Rasam, and Payasam.", 620.0, 7.0, 0.0, 360.0, 15.0, 14.0, 110.0, 9.5),
        ("Kerala Fish Curry Meals", 180.00, non_veg, lunch, "/media/food_photos/kerala_fish_curry_meals.jpg", "Full Kerala Matta rice meals plate served with spicy red kokum fish curry, thoran, moru, and papad.", 480.0, 1.5, 45.0, 350.0, 25.0, 12.0, 68.0, 5.5),
        ("Kerala Chicken Curry Meals", 175.00, non_veg, lunch, "/media/food_photos/kerala_chicken_curry_meals.jpg", "Full Kerala Matta rice meals plate served with Nadan roasted coconut chicken curry, thoran, moru, and papad.", 510.0, 1.5, 60.0, 380.0, 28.0, 16.0, 65.0, 4.5),
        ("Kerala Beef Curry Meals", 185.00, non_veg, lunch, "/media/food_photos/kerala_beef_curry_meals.jpg", "Full Kerala Matta rice meals plate served with slow-roasted spicy coconut beef curry, cabbage thoran, moru, and papad.", 560.0, 1.0, 70.0, 420.0, 32.0, 22.0, 62.0, 4.0),
        ("Kerala Mutton Curry Meals", 210.00, non_veg, lunch, "/media/food_photos/kerala_mutton_curry_meals.jpg", "Full Kerala Matta rice meals plate served with rich spiced Nadan mutton curry, vegetable thoran, and moru.", 590.0, 1.2, 75.0, 440.0, 30.0, 24.0, 64.0, 4.2),
        ("Kerala Meals with Parippu Curry", 150.00, veg, lunch, "/media/food_photos/kerala_meals_with_parippu_curry.jpg", "Full Kerala Matta rice vegetarian meals plate served with yellow moong dal parippu curry, ghee, thoran, and papad.", 440.0, 2.0, 0.0, 310.0, 14.0, 9.0, 76.0, 7.5),
        ("Matta Rice with Fish Curry", 160.00, non_veg, lunch, "/media/food_photos/fish_curry.png", "Home-cooked red Matta rice served with spicy tangy Kerala kokum fish curry.", 440.0, 1.0, 40.0, 320.0, 24.0, 10.0, 64.0, 5.0),
        ("Matta Rice with Beef Fry", 170.00, non_veg, lunch, "/media/food_photos/matta_rice_with_beef_fry.jpg", "Steamed Kerala red Matta rice served with dark spicy Kerala beef fry roasted with coconut chips.", 520.0, 0.8, 68.0, 390.0, 30.0, 20.0, 60.0, 4.0),
        ("Matta Rice with Chicken Curry", 165.00, non_veg, lunch, "/media/food_photos/matta_rice_with_chicken_curry.jpg", "Steamed red Matta rice served with Kerala roasted coconut Nadan chicken curry.", 480.0, 1.2, 58.0, 360.0, 26.0, 15.0, 62.0, 4.2),
        ("Rice with Kerala Fish Fry", 175.00, non_veg, lunch, "/media/food_photos/fish_fry_meals.png", "Kerala Matta rice served with crispy pan-fried spicy fish fry and coconut vegetable thoran.", 490.0, 1.0, 55.0, 370.0, 27.0, 16.0, 61.0, 4.5),
        ("Rice with Karimeen Curry", 250.00, non_veg, lunch, "/media/food_photos/Banana Leaf Karimeen Pollichathu & Matta Rice.png", "Kerala Matta rice served with authentic spicy Kottayam Karimeen (pearl spot fish) curry.", 530.0, 1.5, 60.0, 400.0, 32.0, 18.0, 60.0, 4.0),
        ("Rice with Meen Peera", 160.00, non_veg, lunch, "/media/food_photos/rice_with_meen_peera.jpg", "Kerala Matta rice served with small anchovies cooked with shredded coconut, foliage, and kudampuli.", 430.0, 1.0, 45.0, 330.0, 25.0, 11.0, 58.0, 4.8),
        ("Rice with Beef Roast", 175.00, non_veg, lunch, "/media/food_photos/rice_with_beef_roast.jpg", "Kerala Matta rice served with caramelized onion and coconut chip spicy Kerala beef roast.", 540.0, 1.0, 70.0, 410.0, 31.0, 21.0, 60.0, 4.0),
        ("Rice with Chicken Fry", 170.00, non_veg, lunch, "/media/food_photos/rice_with_chicken_fry.jpg", "Kerala Matta rice served with crispy deep-fried spicy Nadan Kerala chicken fry.", 500.0, 1.0, 62.0, 380.0, 28.0, 18.0, 58.0, 4.0),
        ("Kappa and Fish Curry", 180.00, non_veg, lunch, "/media/food_photos/Kudampuli Mathi Fish Curry & Tapioca (Kappa).png", "Mashed boiled tapioca served with authentic tangy Malabar kokum fish curry.", 480.0, 1.0, 45.0, 360.0, 26.0, 14.0, 62.0, 6.0),
        ("Matta Rice with Vegetable Thoran & Avial", 145.00, veg, lunch, "/media/food_photos/Kachiya Moru Curry & Vendakka Thoran Meal.png", "Steamed Matta rice served with fresh Okra (Vendakka) Thoran, Avial, and seasoned buttermilk curry.", 390.0, 1.5, 0.0, 210.0, 11.0, 5.5, 68.0, 7.0),

        # SNACKS (16 items)
        ("Pazham Pori", 40.00, veg, snack, "/media/food_photos/Hot Pazham Pori (Banana Fritters) & Chai.png", "Crispy deep-fried golden ripe nendran banana fritters.", 210.0, 14.0, 0.0, 40.0, 2.5, 6.0, 38.0, 3.0),
        ("Parippu Vada", 35.00, veg, snack, "/media/food_photos/paripuvada.png", "Crunchy coarse chana dal savory fritters seasoned with ginger, green chillies, and curry leaves.", 190.0, 0.5, 0.0, 85.0, 6.0, 7.0, 26.0, 4.0),
        ("Uzhunnu Vada", 35.00, veg, snack, "/media/food_photos/uzhunnu_vada.jpg", "Golden crispy fried savory urad dal donut fritters served with coconut chutney.", 180.0, 0.5, 0.0, 90.0, 5.0, 6.5, 25.0, 3.5),
        ("Unniyappam", 50.00, dessert, snack, "/media/food_photos/Traditional Rice Unniyappam (4 pcs).png", "Sweet jaggery, banana, and roasted coconut bits deep fried fritters (4 pcs).", 250.0, 18.0, 0.0, 30.0, 3.0, 7.0, 44.0, 2.0),
        ("Neyyappam", 50.00, dessert, snack, "/media/food_photos/neyyappam.png", "Sweet brown rice flour and jaggery fritter fried in ghee.", 260.0, 18.0, 12.0, 35.0, 3.5, 8.0, 43.0, 2.0),
        ("Sukhiyan", 45.00, veg, snack, "/media/food_photos/sukhiyan.jpg", "Sweet green gram and jaggery stuffed dumplings dipped in batter and fried golden.", 230.0, 10.0, 0.0, 45.0, 6.0, 5.5, 39.0, 4.5),
        ("Bonda", 40.00, veg, snack, "/media/food_photos/bonda.jpg", "Sweet ripe banana and wheat batter deep-fried golden round fritters.", 200.0, 12.0, 0.0, 35.0, 3.0, 5.0, 36.0, 2.5),
        ("Ela Ada", 55.00, veg, snack, "/media/food_photos/Steamed Ela Ada (Jaggery & Coconut in Banana Leaf).png", "Healthy steamed rice parcel filled with melted jaggery, grated coconut, and cardamom.", 195.0, 15.0, 0.0, 20.0, 3.0, 4.0, 37.0, 3.5),
        ("Kozhukatta", 45.00, veg, snack, "/media/food_photos/kozhukatta.jpg", "Steamed white rice flour dumplings filled with sweet jaggery and coconut filling.", 180.0, 14.0, 0.0, 15.0, 2.5, 3.5, 35.0, 2.8),
        ("Achappam", 50.00, veg, snack, "/media/food_photos/achappam.jpg", "Crisp flower-shaped rose cookies made of rice flour, coconut milk, and sesame seeds.", 210.0, 6.0, 0.0, 25.0, 2.0, 9.0, 30.0, 1.5),
        ("Murukku", 45.00, veg, snack, "/media/food_photos/murukku.jpg", "Crunchy spiral savory rice flour and sesame seed snack.", 220.0, 0.5, 0.0, 80.0, 3.0, 10.0, 32.0, 2.0),
        ("Banana Chips", 60.00, veg, snack, "/media/food_photos/banana_chips.jpg", "Crisp thin yellow raw Nendran banana slices fried in pure coconut oil.", 270.0, 2.0, 0.0, 95.0, 2.0, 14.0, 34.0, 3.0),
        ("Sharkara Varatti", 65.00, dessert, snack, "/media/food_photos/sharkara_varatti.jpg", "Thick cut jaggery, ginger, and cardamom coated fried banana chips.", 290.0, 22.0, 0.0, 40.0, 2.2, 12.0, 42.0, 3.2),
        ("Mulaku Bajji", 40.00, veg, snack, "/media/food_photos/mulaku_bajji.jpg", "Long green chillies dipped in spiced gram flour batter and deep fried golden.", 180.0, 1.0, 0.0, 110.0, 3.5, 8.0, 24.0, 2.5),
        ("Ulli Vada", 40.00, veg, snack, "/media/food_photos/ulli_vada.jpg", "Crispy fried thin-sliced onion fritters with green chillies and curry leaves.", 195.0, 2.0, 0.0, 120.0, 3.0, 9.0, 26.0, 2.2),
        ("Boiled Green Gram (Cherupayar Sundal)", 45.00, veg, snack, "/media/food_photos/Nadan Matta Rice Kanji & Payar.png", "Healthy boiled green gram tossed with grated coconut, mustard seeds, and curry leaves.", 160.0, 0.5, 0.0, 60.0, 9.0, 1.5, 28.0, 6.0),

        # DINNER (16 items)
        ("Kerala Parotta with Chicken Curry", 150.00, non_veg, dinner, "/media/food_photos/kerala_parotta_with_chicken_curry.jpg", "Soft multi-layered Kerala porotta served with rich spiced Nadan chicken curry.", 490.0, 2.0, 60.0, 370.0, 28.0, 18.0, 54.0, 5.0),
        ("Kerala Parotta with Beef Curry", 160.00, non_veg, dinner, "/media/food_photos/Kerala Porotta & Beef Roast.png", "Flaky Kerala porotta served with spicy slow-roasted coconut beef curry.", 540.0, 1.5, 68.0, 410.0, 30.0, 22.0, 52.0, 4.0),
        ("Appam with Vegetable Stew", 90.00, veg, dinner, "/media/food_photos/appam_with_vegetable_stew.jpg", "Lacy soft coconut rice appams served with mild coconut milk vegetable stew.", 270.0, 2.0, 0.0, 95.0, 4.5, 6.5, 48.0, 3.5),
        ("Appam with Mutton Stew", 195.00, non_veg, dinner, "/media/food_photos/appam_with_mutton_stew.jpg", "Lacy soft appams paired with tender mutton chunks cooked in aromatic coconut milk stew.", 480.0, 2.0, 70.0, 380.0, 26.0, 19.0, 46.0, 2.5),
        ("Idiyappam with Egg Curry", 95.00, non_veg, dinner, "/media/food_photos/idiyappam_with_egg_curry.jpg", "Steamed string hoppers served with delicious egg curry.", 340.0, 3.0, 185.0, 280.0, 12.0, 10.0, 50.0, 2.5),
        ("Idiyappam with Vegetable Curry", 85.00, veg, dinner, "/media/food_photos/idiyappam_with_egg_curry.jpg", "Steamed rice string hoppers served with mixed vegetable coconut kurma.", 260.0, 1.5, 0.0, 110.0, 5.0, 4.0, 48.0, 4.0),
        ("Appam with Egg Curry", 90.00, non_veg, dinner, "/media/food_photos/appam_egg_curry.png", "Soft fluffy coconut appams served with spicy Kerala egg roast curry.", 330.0, 2.5, 185.0, 270.0, 12.0, 9.5, 46.0, 2.5),
        ("Kappa with Beef Curry", 175.00, non_veg, dinner, "/media/food_photos/kappa_biriyani.png", "Boiled seasoned tapioca (Kappa) served with spicy roasted Kerala coconut beef curry.", 530.0, 1.5, 65.0, 420.0, 28.0, 20.0, 62.0, 4.5),
        ("Kappa with Fish Curry", 170.00, non_veg, dinner, "/media/food_photos/Kudampuli Mathi Fish Curry & Tapioca (Kappa).png", "Boiled mashed tapioca served with spicy red Malabar kokum fish curry.", 470.0, 1.0, 45.0, 350.0, 25.0, 13.0, 60.0, 5.5),
        ("Porotta with Egg Curry", 95.00, non_veg, dinner, "/media/food_photos/kerala_parotta_with_egg_curry.jpg", "Hot flaky Kerala parotta served with spicy egg roast curry.", 380.0, 2.0, 185.0, 310.0, 13.0, 15.0, 48.0, 2.0),
        ("Vellayappam with Beef Curry", 155.00, non_veg, dinner, "/media/food_photos/vellayappam_with_beef_curry.jpg", "Soft fluffy white fermented rice appams served with spicy slow-roasted Kerala beef curry.", 460.0, 2.0, 65.0, 370.0, 27.0, 17.0, 48.0, 2.5),
        ("Pathiri with Chicken Curry", 150.00, non_veg, dinner, "/media/food_photos/pathiri_with_chicken_curry.jpg", "Thin soft Malabar rice rotis (Pathiri) served with rich roasted coconut chicken curry.", 450.0, 2.0, 58.0, 350.0, 25.0, 15.0, 54.0, 3.0),
        ("Chapati with Dal Curry", 80.00, veg, dinner, "/media/food_photos/3pcs chapathi chicken.jpg", "Whole wheat soft chapatis served with comforting yellow lentil (dal) curry.", 290.0, 1.0, 0.0, 160.0, 9.0, 5.0, 50.0, 6.0),
        ("Chapati with Vegetable Curry", 85.00, veg, dinner, "/media/food_photos/Soft Wheat Chappathi & Paneer Butter Masala.png", "Whole wheat chapatis served with coconut vegetable kurma.", 310.0, 1.5, 0.0, 170.0, 8.0, 6.0, 52.0, 5.5),
        ("Vegetable Dosa with Coconut Chutney", 75.00, veg, dinner, "/media/food_photos/Crispy Thattu Dosa & Coconut Chutney.png", "Crispy rice crepe filled with seasoned vegetables, served with coconut chutney.", 260.0, 1.2, 0.0, 140.0, 6.0, 4.5, 46.0, 3.5),
        ("Idli with Vegetable Sambar", 65.00, veg, dinner, "/media/food_photos/idli_with_sambar.jpg", "Soft fluffy steamed rice idlis served with hot vegetable sambar.", 210.0, 1.0, 0.0, 130.0, 5.0, 2.0, 42.0, 3.0)
    ]

    foods_list = []
    for idx, (name, price, cat, session, img, desc, cal, sug, chol, sod, prot, fat, carb, fib) in enumerate(foods_data, start=1):
        f = FoodItem.objects.create(
            chef=chef_user,
            name=name,
            price=price,
            category=cat,
            meal_session=session,
            stock_quantity=20,
            is_available=True,
            image=img,
            description=desc
        )
        NutritionInfo.objects.create(
            food_item=f,
            calories=cal,
            sugar=sug,
            cholesterol=chol,
            sodium=sod,
            protein=prot,
            fat=fat,
            carbohydrates=carb,
            fiber=fib
        )
        foods_list.append(f)

    # 6. Create Coupons
    print("Creating coupons...")
    Coupon.objects.create(code='WELCOME15', discount_percentage=15.00, min_purchase_amount=100.00, is_active=True, expiry_date='2027-12-31')
    Coupon.objects.create(code='FESTIVAL25', discount_percentage=25.00, min_purchase_amount=150.00, is_active=True, expiry_date='2027-12-31')

    # Assign variables for review sentiment examples
    f1 = foods_list[0]  # First created food item (Puttu and Kadala Curry)
    f12 = None
    # Find a non-veg lunch item for negative review (e.g., Beef Roast)
    for item in foods_list:
        if "Beef" in item.name:
            f12 = item
            break
    if not f12:
        f12 = foods_list[1]  # fallback

    # 7. Create Review Sentiments (AI Naive Bayes simulation values)
    print("Creating review sentiments...")
    ReviewSentiment.objects.create(user=cust_user, food_item=f1, rating=5, review_text="Excellent taste, extremely healthy breakfast. Loved it!", sentiment='positive', confidence_score=0.98)
    ReviewSentiment.objects.create(user=cust_user, food_item=f12, rating=2, review_text="The beef roast was way too oily and extremely salty. Disappointed.", sentiment='negative', confidence_score=0.95)

    # 8. Create Customer Behavior
    print("Creating customer behaviors...")
    CustomerBehavior.objects.create(
        user=cust_user, total_orders_count=1, average_order_value=50.00,
        most_ordered_session=breakfast, most_ordered_category=veg, behavior_segment='occasional'
    )

    # 9. Create AI Demand/Waste Predictions
    print("Creating AI forecast tables...")
    for food in foods_list:
        FoodDemandForecast.objects.create(food_item=food, forecast_date=datetime.date.today(), predicted_quantity=8.5, confidence_score=0.89)
        FoodWastePrediction.objects.create(food_item=food, prediction_date=datetime.date.today(), predicted_waste_quantity=1.2)
        StockPrediction.objects.create(food_item=food, prediction_date=datetime.date.today(), predicted_days_until_out_of_stock=3.5, stock_needed_refill=4)

    # 10. Simulate active assigned & out-for-delivery orders for Courier
    print("Creating active delivery assignments for Courier...")
    
    # Active Order 1: Assigned (Order ID: VR-20260825-UTQD, Puttu and Kadala Curry, Qty 1)
    active_order_1 = Order.objects.create(
        user=cust_user, total_amount=70.00, status='assigned',
        latitude=10.025, longitude=76.315, delivery_address=''
    )
    active_order_1.order_id = "VR-20260825-UTQD"
    active_order_1.save()
    OrderItem.objects.create(order=active_order_1, food_item=f1, quantity=1, price=70.00)
    Payment.objects.create(order=active_order_1, payment_method='cod', transaction_id='TXN-ACTIVE-1', status='pending', amount=70.00)
    
    DeliveryAssignment.objects.create(
        order=active_order_1, delivery_boy=courier_profile, status='assigned',
        assigned_at=timezone.now() - datetime.timedelta(minutes=10),
        predicted_delivery_time=25.0
    )

    # Active Order 2: Out for Delivery (In Transit)
    active_order_2 = Order.objects.create(
        user=cust_user, total_amount=150.00, status='in_transit',
        latitude=10.035, longitude=76.305, delivery_address=''
    )
    f_dosa = foods_list[2] if len(foods_list) > 2 else f1
    OrderItem.objects.create(order=active_order_2, food_item=f_dosa, quantity=2, price=75.00)
    Payment.objects.create(order=active_order_2, payment_method='upi', transaction_id='UPI-ACTIVE-2', status='success', amount=150.00)
    
    assign2 = DeliveryAssignment.objects.create(
        order=active_order_2, delivery_boy=courier_profile, status='in_transit',
        assigned_at=timezone.now() - datetime.timedelta(minutes=15),
        picked_up_at=timezone.now() - datetime.timedelta(minutes=5),
        predicted_delivery_time=20.0
    )
    GPSLocationTracking.objects.create(delivery_assignment=assign2, latitude=10.015, longitude=76.325)
    GPSLocationTracking.objects.create(delivery_assignment=assign2, latitude=10.022, longitude=76.318)

    # 11. Simulate a completed order
    print("Creating a simulated completed delivery assignment for regression metrics...")
    old_order = Order.objects.create(
        user=cust_user, total_amount=70.00, status='delivered',
        latitude=10.025, longitude=76.315, delivery_address=''
    )
    OrderItem.objects.create(order=old_order, food_item=f1, quantity=1, price=70.00)
    Payment.objects.create(order=old_order, payment_method='cod', transaction_id='TXN-SIMULATED-1', status='success', amount=70.00)
    
    # Assign and complete
    assignment = DeliveryAssignment.objects.create(
        order=old_order, delivery_boy=courier_profile, status='delivered',
        assigned_at=timezone.now() - datetime.timedelta(minutes=45),
        picked_up_at=timezone.now() - datetime.timedelta(minutes=35),
        delivered_at=timezone.now() - datetime.timedelta(minutes=10),
        predicted_delivery_time=20.0,
        actual_delivery_time=25.0
    )
    
    # Location track breadcrumbs
    GPSLocationTracking.objects.create(delivery_assignment=assignment, latitude=10.015, longitude=76.325)
    GPSLocationTracking.objects.create(delivery_assignment=assignment, latitude=10.020, longitude=76.320)
    GPSLocationTracking.objects.create(delivery_assignment=assignment, latitude=10.025, longitude=76.315)

    print("Database seeding completed successfully!")

if __name__ == '__main__':
    seed_database()
