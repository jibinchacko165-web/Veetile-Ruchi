from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from health.models import HealthProfile, HealthRecommendation
from food.models import FoodItem, MealSession, Category, NutritionInfo
from ai_models.ml_engine import recommend_health_and_time_aware_foods, is_food_excluded_by_allergens


class HealthSettingsAndRecommendationsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='health_customer',
            email='health_customer@example.com',
            password='Password123!',
            role='customer'
        )
        self.chef = User.objects.create_user(
            username='home_chef',
            email='chef@example.com',
            password='Password123!',
            role='chef'
        )
        
        self.session_breakfast = MealSession.objects.create(
            name='Breakfast', start_time='07:00:00', end_time='11:00:00'
        )
        self.session_lunch = MealSession.objects.create(
            name='Lunch', start_time='12:00:00', end_time='16:00:00'
        )
        
        self.cat_veg = Category.objects.create(name='Vegetarian')
        self.cat_nonveg = Category.objects.create(name='Non-Vegetarian')
        
        # Dish 1: Healthy steamed vegetarian dish (low sugar, low sodium, low fat)
        self.food_puttu = FoodItem.objects.create(
            chef=self.chef,
            name='Puttu with Kadala Curry',
            description='Steamed rice flour cylinders layered with grated coconut served with black chickpea curry.',
            price=90.00,
            category=self.cat_veg,
            meal_session=self.session_breakfast,
            is_available=True,
            stock_quantity=15,
            is_vegetarian=True
        )
        NutritionInfo.objects.create(
            food_item=self.food_puttu,
            calories=330.0,
            protein=11.5,
            carbohydrates=54.0,
            total_sugars=3.2,
            added_sugars=0.0,
            total_fat=5.8,
            saturated_fat=1.9,
            sodium=220.0,
            ingredients='Rice flour, grated coconut, black chickpeas, onions, ginger, turmeric',
            allergens='None',
            serving_size='1 portion (200g)',
            cooking_method='Steamed'
        )
        
        # Dish 2: Fish curry (non-vegetarian, contains fish)
        self.food_fish = FoodItem.objects.create(
            chef=self.chef,
            name='Matta Rice with Sardine Curry',
            description='Parboiled red rice served with traditional Kerala sardine curry in spicy kokum gravy.',
            price=140.00,
            category=self.cat_nonveg,
            meal_session=self.session_lunch,
            is_available=True,
            stock_quantity=10,
            is_vegetarian=False
        )
        NutritionInfo.objects.create(
            food_item=self.food_fish,
            calories=440.0,
            protein=24.0,
            carbohydrates=62.0,
            total_sugars=2.1,
            added_sugars=0.0,
            total_fat=8.5,
            saturated_fat=2.2,
            sodium=380.0,
            ingredients='Kerala matta rice, sardines, kokum, fenugreek, chili, curry leaves',
            allergens='Fish',
            serving_size='1 meal (400g)',
            cooking_method='Simmered'
        )

        # Dish 3: High sodium / high sugar sweet item
        self.food_sweet = FoodItem.objects.create(
            chef=self.chef,
            name='Sweet Kozhukatta',
            description='Steamed rice dumplings filled with grated coconut and melted jaggery syrup.',
            price=50.00,
            category=self.cat_veg,
            meal_session=self.session_breakfast,
            is_available=True,
            stock_quantity=10,
            is_vegetarian=True
        )
        NutritionInfo.objects.create(
            food_item=self.food_sweet,
            calories=280.0,
            protein=4.0,
            carbohydrates=58.0,
            total_sugars=22.0,
            added_sugars=18.0,
            total_fat=4.5,
            saturated_fat=3.0,
            sodium=180.0,
            ingredients='Rice flour, jaggery, coconut, cardamom',
            allergens='None',
            serving_size='2 pieces',
            cooking_method='Steamed'
        )

    def test_health_profile_save_and_reload(self):
        """Verify customer can save and reload complete health settings."""
        self.client.login(username='health_customer', password='Password123!')
        
        response = self.client.post(reverse('health_profile'), {
            'diabetes_conscious': 'on',
            'cholesterol_conscious': 'on',
            'blood_pressure_conscious': 'on',
            'reduced_sugar': 'on',
            'lower_saturated_fat': 'on',
            'reduced_sodium': 'on',
            'dietary_preference': 'veg',
            'allergies': 'peanuts, shellfish',
            'dislikes': 'bitter gourd',
            'daily_calorie_target': '1800',
            'enable_recommendations': 'on'
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        profile = HealthProfile.objects.get(user=self.user)
        self.assertTrue(profile.diabetes_conscious)
        self.assertTrue(profile.cholesterol_conscious)
        self.assertTrue(profile.blood_pressure_conscious)
        self.assertTrue(profile.reduced_sugar)
        self.assertTrue(profile.lower_saturated_fat)
        self.assertTrue(profile.reduced_sodium)
        self.assertEqual(profile.dietary_preference, 'veg')
        self.assertIn('peanuts', profile.allergies)
        self.assertIn('bitter gourd', profile.dislikes)
        self.assertEqual(profile.daily_calorie_target, 1800.0)

    def test_allergen_exclusion_filter(self):
        """Verify that dishes containing specified allergens are excluded from recommendations."""
        profile = HealthProfile.objects.create(
            user=self.user,
            allergies='fish, sardines',
            dietary_preference='any'
        )
        
        # Test allergen helper function
        self.assertTrue(is_food_excluded_by_allergens(self.food_fish, ['fish']))
        self.assertFalse(is_food_excluded_by_allergens(self.food_puttu, ['fish']))
        
        # Test recommendation engine excludes fish curry
        recs, reason = recommend_health_and_time_aware_foods(
            [self.food_puttu, self.food_fish],
            profile,
            active_session_name='Lunch'
        )
        
        rec_ids = [f.id for f in recs]
        self.assertNotIn(self.food_fish.id, rec_ids)

    def test_diabetes_filter_excludes_high_sugar(self):
        """Verify that diabetes preference excludes high-sugar items."""
        profile = HealthProfile.objects.create(
            user=self.user,
            diabetes_conscious=True,
            dietary_preference='veg'
        )
        
        recs, reason = recommend_health_and_time_aware_foods(
            [self.food_puttu, self.food_sweet],
            profile,
            active_session_name='Breakfast'
        )
        
        rec_ids = [f.id for f in recs]
        self.assertIn(self.food_puttu.id, rec_ids)
        self.assertNotIn(self.food_sweet.id, rec_ids)

    def test_recommendation_disclaimer_present(self):
        """Verify recommendations include proper general guidance note rather than medical claims."""
        profile = HealthProfile.objects.create(
            user=self.user,
            diabetes_conscious=True,
            cholesterol_conscious=True
        )
        
        recs, reason = recommend_health_and_time_aware_foods(
            [self.food_puttu],
            profile,
            active_session_name='Breakfast'
        )
        
        self.assertIn('General dietary guidance', reason)
