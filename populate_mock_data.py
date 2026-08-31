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
    
    # Create 9 distinct courier profiles with vehicle numbers for staff selection
    couriers = []
    vehicle_nums = [
        'KL-07-CD-1001', 'KL-07-CD-1002', 'KL-07-CD-1003',
        'KL-07-CD-1004', 'KL-07-CD-1005', 'KL-07-CD-1006',
        'KL-07-CD-1007', 'KL-07-CD-1008', 'KL-07-CD-1009'
    ]
    for i, v_num in enumerate(vehicle_nums, start=1):
        uname = 'courier' if i == 1 else f'courier{i}'
        u = User.objects.create_user(username=uname, email=f'{uname}@ruchi.com', password='password123', role='delivery_boy', dob='1996-08-12')
        p = DeliveryBoyProfile.objects.create(user=u, vehicle_number=v_num, status='available')
        couriers.append(p)
    courier_profile = couriers[0] # primary courier profile for initial simulated assignment
    
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

    # 5. Create 50 Authentic Malayali Food Items & Nutrition Specs
    print("Creating 50 authentic homemade Kerala food items...")
    
    foods_data = [
        # BREAKFAST (15 items)
        ("Puttu and Kadala Curry", 70.00, veg, breakfast, "/media/food_photos/kerala puttu kadala curry.png", "Steamed rice flour puttu cylinders layered with coconut, served with spicy black chickpea curry.", 310.0, 1.5, 0.0, 110.0, 9.0, 4.0, 58.0, 7.0),
        ("Appam and Vegetable Stew", 85.00, veg, breakfast, "/media/food_photos/Palappam & Vegetable Stew.png", "Lacy soft coconut rice pancakes served with mild creamy coconut milk vegetable stew.", 270.0, 2.0, 0.0, 95.0, 4.5, 6.5, 48.0, 3.5),
        ("Palappam and Chicken Stew", 140.00, non_veg, breakfast, "/media/food_photos/Palapam chicken.png", "Soft fermented rice hoppers served with tender chicken cooked in coconut milk stew.", 420.0, 2.5, 65.0, 310.0, 22.0, 16.0, 44.0, 2.0),
        ("Idiyappam and Egg Curry", 90.00, non_veg, breakfast, "/media/food_photos/Kerala Idiyappam & Egg Roast.png", "Soft steamed string hoppers accompanied by caramelised onion spiced egg roast.", 340.0, 3.0, 185.0, 280.0, 12.0, 10.0, 50.0, 2.5),
        ("Idiyappam and Vegetable Kurma", 80.00, veg, breakfast, "/media/food_photos/Soft Malabar Pathiri & Veg Kurma.png", "Steamed string hoppers served with aromatic coconut vegetable kurma.", 250.0, 1.8, 0.0, 120.0, 5.0, 5.0, 46.0, 3.0),
        ("Dosa and Sambar", 65.00, veg, breakfast, "/media/food_photos/Crispy Thattu Dosa & Coconut Chutney.png", "Golden crispy rice-lentil crepe served with authentic Kerala vegetable sambar and chutney.", 240.0, 1.2, 0.0, 150.0, 5.5, 4.0, 45.0, 3.0),
        ("Masala Dosa", 75.00, veg, breakfast, "/media/food_photos/thattu_dosa.png", "Crispy golden crepe stuffed with spiced potato masala, served with coconut chutney.", 280.0, 1.5, 0.0, 180.0, 6.0, 7.0, 50.0, 3.5),
        ("Ney Pathiri", 75.00, veg, breakfast, "/media/food_photos/Soft Malabar Pathiri & Veg Kurma.png", "Deep-fried seasoned rice flour flatbread infused with ghee, onions, and cumin.", 290.0, 1.0, 0.0, 140.0, 4.0, 10.0, 44.0, 2.0),
        ("Ulli Dosa", 70.00, veg, breakfast, "/media/food_photos/Crispy Thattu Dosa & Coconut Chutney.png", "Thattu dosa topped with caramelized shallots, green chillies, and curry leaves.", 250.0, 1.5, 0.0, 160.0, 5.0, 5.0, 46.0, 2.8),
        ("Chakka Puttu", 85.00, veg, breakfast, "/media/food_photos/puttu_kadala.png", "Steamed rice flour puttu layered with sweet ripe jackfruit bits and fresh coconut.", 260.0, 12.0, 0.0, 45.0, 4.0, 2.0, 56.0, 4.0),
        ("Ragi Puttu", 75.00, veg, breakfast, "/media/food_photos/Steam Puttu & Kuttanadan Duck Curry.png", "Healthy finger millet puttu steamed with grated coconut, rich in iron and fiber.", 220.0, 0.8, 0.0, 35.0, 5.5, 2.5, 48.0, 6.5),
        ("Ada", 60.00, veg, breakfast, "/media/food_photos/Steamed Ela Ada (Jaggery & Coconut in Banana Leaf).png", "Steamed rice parcel stuffed with sweet melted jaggery, coconut, and cardamom.", 195.0, 15.0, 0.0, 20.0, 3.0, 4.0, 37.0, 3.5),
        ("Kappa and Fish Curry", 180.00, non_veg, breakfast, "/media/food_photos/Kudampuli Mathi Fish Curry & Tapioca (Kappa).png", "Mashed boiled tapioca served with authentic tangy Malabar kokum fish curry.", 480.0, 1.0, 45.0, 360.0, 26.0, 14.0, 62.0, 6.0),
        ("Paniyaram", 55.00, veg, breakfast, "/media/food_photos/Traditional Rice Unniyappam (4 pcs).png", "Crispy outside, soft inside seasoned rice batter dumplings served with tomato chutney.", 210.0, 1.0, 0.0, 120.0, 4.5, 4.0, 38.0, 2.0),
        ("Kerala Upma", 50.00, veg, breakfast, "/media/food_photos/Palappam & Vegetable Stew.png", "Roasted semolina cooked with mustard seeds, ginger, curry leaves, and grated coconut.", 230.0, 1.0, 0.0, 110.0, 5.0, 5.0, 40.0, 3.0),

        # LUNCH (15 items)
        ("Traditional Kerala Meals", 220.00, veg, lunch, "/media/food_photos/Kerala Traditional Sadya Feast.png", "Authentic Kerala Matta rice lunch feast on banana leaf with Avial, Thoran, Sambar, and Payasam.", 590.0, 6.0, 0.0, 340.0, 14.0, 12.0, 105.0, 9.0),
        ("Matta Rice and Fish Curry", 160.00, non_veg, lunch, "/media/food_photos/fish_curry.png", "Home-cooked red Matta rice served with spicy tangy Kerala kokum fish curry.", 440.0, 1.0, 40.0, 320.0, 24.0, 10.0, 64.0, 5.0),
        ("Fish Curry Meals", 180.00, non_veg, lunch, "/media/food_photos/Kudampuli Mathi Fish Curry & Tapioca (Kappa).png", "Full Kerala red rice meals served with spicy sardine fish curry, cabbage thoran, and moru.", 480.0, 1.5, 45.0, 350.0, 25.0, 12.0, 68.0, 5.5),
        ("Chicken Curry Meals", 170.00, non_veg, lunch, "/media/food_photos/3pcs chapathi chicken.jpg", "Kerala Matta rice meals accompanied by Nadan roasted coconut chicken curry.", 510.0, 1.5, 60.0, 380.0, 28.0, 16.0, 65.0, 4.5),
        ("Beef Curry Meals", 180.00, non_veg, lunch, "/media/food_photos/Kerala Porotta & Beef Roast.png", "Kerala red rice meals paired with slow-roasted spicy coconut beef curry.", 560.0, 1.0, 70.0, 420.0, 32.0, 22.0, 62.0, 4.0),
        ("Prawn Curry Meals", 210.00, non_veg, lunch, "/media/food_photos/fish_fry_meals.png", "Kerala Matta rice meals served with rich Chemmeen coconut prawn curry.", 490.0, 1.2, 85.0, 390.0, 26.0, 14.0, 60.0, 4.2),
        ("Sambar and Avial", 120.00, veg, lunch, "/media/food_photos/Kachiya Moru Curry & Vendakka Thoran Meal.png", "Classic combination of mixed vegetable coconut Avial and hot drumstick Sambar.", 320.0, 2.0, 0.0, 210.0, 8.0, 6.0, 58.0, 7.0),
        ("Thoran and Olan", 110.00, veg, lunch, "/media/food_photos/Kachiya Moru Curry & Vendakka Thoran Meal.png", "Cabbage coconut stir-fry paired with ash gourd red cowpea mild coconut milk Olan.", 280.0, 1.5, 0.0, 180.0, 6.5, 5.0, 52.0, 6.0),
        ("Kootu Curry", 115.00, veg, lunch, "/media/food_photos/kerala_sadya.png", "Thick rich curry made of raw plantain, black chickpeas, roasted coconut, and jaggery.", 310.0, 4.0, 0.0, 160.0, 7.5, 5.5, 55.0, 6.5),
        ("Moru Curry", 95.00, veg, lunch, "/media/food_photos/Kachiya Moru Curry & Vendakka Thoran Meal.png", "Seasoned buttermilk curry cooked with turmeric, mustard, ginger, and curry leaves.", 180.0, 1.0, 0.0, 140.0, 4.0, 3.5, 32.0, 2.0),
        ("Meen Pollichathu", 260.00, non_veg, lunch, "/media/food_photos/Banana Leaf Karimeen Pollichathu & Matta Rice.png", "Pearl spot fish marinated in spicy tomato-onion masala pan roasted inside banana leaf.", 520.0, 2.0, 60.0, 390.0, 32.0, 18.0, 58.0, 4.0),
        ("Karimeen Fry Meals", 250.00, non_veg, lunch, "/media/food_photos/Banana Leaf Karimeen Pollichathu & Matta Rice.png", "Kerala Matta rice meals served with crispy fried whole Karimeen pearl spot fish.", 540.0, 1.0, 65.0, 410.0, 30.0, 20.0, 60.0, 4.5),
        ("Kerala Egg Curry Meals", 140.00, non_veg, lunch, "/media/food_photos/appam_egg_curry.png", "Rice meals served with spicy roasted onion gravy hard boiled egg curry.", 420.0, 2.0, 185.0, 310.0, 16.0, 12.0, 62.0, 4.0),
        ("Vegetable Sadya", 200.00, veg, lunch, "/media/food_photos/kerala_sadya.png", "Traditional vegetarian banana leaf feast featuring 12 side dishes and Payasam.", 560.0, 5.5, 0.0, 320.0, 12.0, 10.0, 100.0, 8.5),
        ("Traditional Kerala Sadya", 240.00, veg, lunch, "/media/food_photos/Kerala Traditional Sadya Feast.png", "Grand festival feast served on banana leaf with Matta rice, Parippu, Ghee, 14 curries.", 620.0, 7.0, 0.0, 360.0, 15.0, 14.0, 110.0, 9.5),

        # EVENING SNACKS (10 items)
        ("Pazham Pori", 40.00, veg, snack, "/media/food_photos/Hot Pazham Pori (Banana Fritters) & Chai.png", "Crispy golden fried ripe banana fritters served with hot Kerala cardamom tea.", 210.0, 14.0, 0.0, 40.0, 2.5, 6.0, 38.0, 3.0),
        ("Parippu Vada", 35.00, veg, snack, "/media/food_photos/paripuvada.png", "Crunchy coarse chana dal savory fritters seasoned with ginger and green chillies.", 190.0, 0.5, 0.0, 85.0, 6.0, 7.0, 26.0, 4.0),
        ("Uzhunnu Vada", 35.00, veg, snack, "/media/food_photos/paripuvada.png", "Golden crispy black gram donut fritters served with coconut chutney.", 180.0, 0.5, 0.0, 90.0, 5.0, 6.5, 25.0, 3.5),
        ("Unniyappam", 50.00, dessert, snack, "/media/food_photos/Traditional Rice Unniyappam (4 pcs).png", "Sweet jaggery, banana, and roasted coconut bits deep fried fritters (4 pcs).", 250.0, 18.0, 0.0, 30.0, 3.0, 7.0, 44.0, 2.0),
        ("Sukhiyan", 45.00, veg, snack, "/media/food_photos/neyyappam.png", "Sweet green gram jaggery dumplings dipped in batter and fried crisp.", 230.0, 10.0, 0.0, 45.0, 6.0, 5.5, 39.0, 4.5),
        ("Ela Ada", 55.00, veg, snack, "/media/food_photos/Steamed Ela Ada (Jaggery & Coconut in Banana Leaf).png", "Healthy steamed rice parcel filled with melted jaggery, grated coconut, and cardamom.", 195.0, 15.0, 0.0, 20.0, 3.0, 4.0, 37.0, 3.5),
        ("Kozhukatta", 45.00, veg, snack, "/media/food_photos/Steamed Ela Ada (Jaggery & Coconut in Banana Leaf).png", "Steamed white rice flour balls stuffed with sweet grated coconut and jaggery.", 180.0, 14.0, 0.0, 15.0, 2.5, 3.5, 35.0, 2.8),
        ("Banana Bonda", 40.00, veg, snack, "/media/food_photos/Hot Pazham Pori (Banana Fritters) & Chai.png", "Sweet ripe banana and wheat batter deep-fried golden round fritters.", 200.0, 12.0, 0.0, 35.0, 3.0, 5.0, 36.0, 2.5),
        ("Achappam", 50.00, veg, snack, "/media/food_photos/neyyappam.png", "Crunchy rosette cookies made from rice flour, coconut milk, and sesame seeds.", 210.0, 6.0, 0.0, 25.0, 2.0, 9.0, 30.0, 1.5),
        ("Kuzhalappam", 50.00, veg, snack, "/media/food_photos/neyyappam.png", "Crispy tube-shaped fried rice flour snack seasoned with cumin and garlic.", 220.0, 1.0, 0.0, 50.0, 2.5, 10.0, 31.0, 1.2),

        # DINNER (10 items)
        ("Chapati and Vegetable Curry", 110.00, veg, dinner, "/media/food_photos/Soft Wheat Chappathi & Paneer Butter Masala.png", "Soft whole wheat chappathis served with healthy mixed vegetable curry.", 340.0, 2.5, 0.0, 210.0, 9.0, 7.0, 58.0, 6.0),
        ("Chapati and Chicken Curry", 150.00, non_veg, dinner, "/media/food_photos/3pcs chapathi chicken.jpg", "Soft whole wheat chappathis served with roasted coconut Nadan chicken curry.", 490.0, 2.0, 60.0, 370.0, 28.0, 18.0, 54.0, 5.0),
        ("Appam and Fish Molee", 190.00, non_veg, dinner, "/media/food_photos/appam_egg_curry.png", "Soft lacy Appams paired with tender fish cooked in mild turmeric coconut milk stew.", 460.0, 2.0, 50.0, 340.0, 25.0, 15.0, 52.0, 3.0),
        ("Idiyappam and Chicken Curry", 160.00, non_veg, dinner, "/media/food_photos/Kerala Idiyappam & Egg Roast.png", "Steamed string hoppers served with spicy coconut Nadan chicken gravy.", 450.0, 2.2, 58.0, 360.0, 26.0, 16.0, 52.0, 3.5),
        ("Kappa and Beef Curry", 180.00, non_veg, dinner, "/media/food_photos/kappa_biriyani.png", "Boiled seasoned tapioca served with slow-roasted spicy coconut beef curry.", 540.0, 1.5, 65.0, 420.0, 28.0, 20.0, 62.0, 4.5),
        ("Pathiri and Chicken Roast", 170.00, non_veg, dinner, "/media/food_photos/Soft Malabar Pathiri & Veg Kurma.png", "Thin Malabar rice rotis served with spicy caramelized onion chicken roast.", 480.0, 2.0, 60.0, 380.0, 26.0, 16.0, 58.0, 3.0),
        ("Puttu and Egg Roast", 110.00, non_veg, dinner, "/media/food_photos/kerala puttu kadala curry.png", "Steamed rice puttu served with spicy caramelized onion Kerala egg roast.", 360.0, 2.5, 185.0, 290.0, 14.0, 11.0, 52.0, 3.5),
        ("Dosa and Coconut Chutney", 75.00, veg, dinner, "/media/food_photos/Crispy Thattu Dosa & Coconut Chutney.png", "Hot crispy dosa served with fresh green coconut chutney and sambar.", 260.0, 1.2, 0.0, 160.0, 6.0, 5.0, 48.0, 3.2),
        ("Kanji and Payar", 80.00, veg, dinner, "/media/food_photos/Nadan Matta Rice Kanji & Payar.png", "Soothing warm red rice porridge served with green gram thoran, papad, and pickle.", 260.0, 0.5, 0.0, 120.0, 7.5, 1.5, 54.0, 5.0),
        ("Vegetable Kurma with Appam", 120.00, veg, dinner, "/media/food_photos/Palappam & Vegetable Stew.png", "Soft lacy rice appams served with rich aromatic vegetable coconut kurma.", 330.0, 2.0, 0.0, 190.0, 7.0, 8.0, 56.0, 4.5)
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
