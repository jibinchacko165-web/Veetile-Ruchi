import os
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from food.models import FoodItem, MealSession, Category, NutritionInfo
from ai_models.ml_engine import predict_health_suitability

class KeralaAuthenticFoodsTestCase(TestCase):
    """
    Test suite verifying authentic Kerala foods, ensuring complete removal
    of circular graphical placeholder cards, duplicate food pictures, and the empty Desserts category.
    """

    EXPECTED_AUTHENTIC_FOODS = [
        # Breakfast
        "Kerala Matta Rice Porridge (Matta Ari Kanji)",
        "Puttu with Green Gram Curry",
        "Ragi Puttu with Cherupayar",
        "Idiyappam with Vegetable Stew",
        "Kerala Vegetable Oats Upma",
        "Idli with Vegetable Sambar",
        # Lunch
        "Kerala Matta Rice with Vegetable Avial",
        "Matta Rice with Fish Curry",
        "Matta Rice with Cherupayar Thoran",
        "Kerala Vegetable Sambar with Rice",
        "Pumpkin Erissery with Matta Rice",
        "Matta Rice with Grilled Kerala-Spiced Fish",
        # Evening Snacks
        "Steamed Kozhukatta with Green Gram Filling",
        "Steamed Ragi Puttu Bites",
    ]

    REMOVED_CIRCULAR_FOODS = [
        "Kerala Steamed Nendran Banana",
        "Vegetable Ada",
        "Roasted Kadala (Black Chickpeas)",
        "Cucumber and Carrot Salad with Kerala Spices",
        "Vegetable Dosa with Sambar",
        "Oats Kanji with Green Gram",
        "Kerala Olan with Matta Rice",
        "Kerala Kalan with a Controlled Rice Portion",
        "Chicken Stew with Vegetables and Appam",
    ]

    REMOVED_CIRCULAR_IMAGE_FILES = [
        "steamed_nendran_banana.jpg",
        "vegetable_ada.jpg",
        "roasted_kadala_chickpeas.jpg",
        "cucumber_carrot_kerala_salad.jpg",
        "vegetable_dosa_sambar.jpg",
        "oats_kanji_green_gram.jpg",
        "kerala_olan_matta_rice.jpg",
        "kerala_kalan_rice.jpg",
        "chicken_stew_vegetables_appam.jpg",
    ]

    def setUp(self):
        self.client = Client()

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        from accounts.models import User
        # Ensure a chef user exists in the test DB
        if not User.objects.filter(role='chef').exists():
            User.objects.create_user(
                username='chef_test',
                email='chef_test@ruchi.com',
                password='Password123!',
                role='chef',
                phone='9876543210'
            )
        call_command('seed_24_kerala_foods')

    def test_desserts_category_completely_removed(self):
        """Verifies that the Desserts category is completely removed and does not render in the catalog."""
        self.assertFalse(
            Category.objects.filter(name__iexact='Desserts').exists(),
            "Category 'Desserts' should NOT exist in the database."
        )
        resp = self.client.get(reverse('food_catalog'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        # Ensure category pill for Desserts is not rendered
        self.assertNotIn("?category=Desserts", content)
        self.assertNotIn(">Desserts<", content)

    def test_duplicate_food_cards_and_images_removed(self):
        """Verifies that duplicate food cards with identical pictures (such as duplicate Kozhukatta with Ela Ada image) are removed."""
        # Ensure duplicate Steamed Kozhukatta (ID 271) with Ela Ada picture is removed
        duplicate_koz = FoodItem.objects.filter(name='Steamed Kozhukatta').exclude(name__icontains='Filling').first()
        self.assertIsNone(duplicate_koz, "Duplicate 'Steamed Kozhukatta' card should not exist.")

        # Ensure Kozhukatta with actual Kozhukatta photo still exists
        real_koz = FoodItem.objects.filter(name='Steamed Kozhukatta with Green Gram Filling').first()
        self.assertIsNotNone(real_koz, "'Steamed Kozhukatta with Green Gram Filling' must exist.")

        # Ensure duplicate kozhukatta.jpg (which had Ela Ada image) is not present
        koz_img = os.path.join(settings.MEDIA_ROOT, 'food_photos', 'kozhukatta.jpg')
        self.assertFalse(os.path.exists(koz_img), "Duplicate kozhukatta.jpg should not exist on disk.")

        # Ensure duplicate soup (ID 311) is not present
        duplicate_soup = FoodItem.objects.filter(name='Mixed Vegetable Soup with Kerala Spices').first()
        self.assertIsNone(duplicate_soup, "Duplicate 'Mixed Vegetable Soup with Kerala Spices' should not exist.")

    def test_circular_placeholder_cards_and_items_completely_removed(self):
        """Verifies that circular graphic placeholder foods and their images are completely removed."""
        # 1. No removed foods exist in DB
        for name in self.REMOVED_CIRCULAR_FOODS:
            food = FoodItem.objects.filter(name=name).first()
            self.assertIsNone(food, f"Circular placeholder food '{name}' should NOT exist in database.")

        # 2. No circular placeholder image files exist on disk in kerala_24
        kerala24_dir = os.path.join(settings.MEDIA_ROOT, "food_photos", "kerala_24")
        for fname in self.REMOVED_CIRCULAR_IMAGE_FILES:
            fpath = os.path.join(kerala24_dir, fname)
            self.assertFalse(os.path.exists(fpath), f"Circular placeholder image '{fname}' should NOT exist on disk.")

    def test_authentic_kerala_foods_exist_with_unique_names(self):
        """Verifies that intended authentic Kerala food records exist and have unique names."""
        found_names = []
        for name in self.EXPECTED_AUTHENTIC_FOODS:
            food = FoodItem.objects.filter(name=name).first()
            self.assertIsNotNone(food, f"Authentic food item '{name}' not found in database.")
            found_names.append(food.name)

        self.assertEqual(len(found_names), len(self.EXPECTED_AUTHENTIC_FOODS))
        self.assertEqual(len(set(found_names)), len(self.EXPECTED_AUTHENTIC_FOODS))

    def test_meal_time_scheduling_windows(self):
        """Verifies that meal session windows match the exact specified schedule."""
        b_sess = MealSession.objects.get(name="Morning Breakfast")
        l_sess = MealSession.objects.get(name="Lunch")
        s_sess = MealSession.objects.get(name="Evening Snacks")
        d_sess = MealSession.objects.get(name="Dinner")

        # Breakfast: 6:30 AM–12:00 PM
        self.assertEqual(str(b_sess.start_time), "06:30:00")
        self.assertEqual(str(b_sess.end_time), "12:00:00")

        # Lunch: 12:00 PM–3:30 PM
        self.assertEqual(str(l_sess.start_time), "12:00:00")
        self.assertEqual(str(l_sess.end_time), "15:30:00")

        # Evening Snacks: 3:30 PM–6:00 PM
        self.assertEqual(str(s_sess.start_time), "15:30:00")
        self.assertEqual(str(s_sess.end_time), "18:00:00")

        # Dinner: 6:00 PM–11:00 PM
        self.assertEqual(str(d_sess.start_time), "18:00:00")
        self.assertEqual(str(d_sess.end_time), "23:00:00")

    def test_every_authentic_item_has_unique_valid_photo(self):
        """Verifies each authentic food has a distinct photo that physically exists on disk."""
        foods = FoodItem.objects.filter(name__in=self.EXPECTED_AUTHENTIC_FOODS)
        image_paths = [f.image for f in foods]

        self.assertEqual(len(image_paths), len(self.EXPECTED_AUTHENTIC_FOODS))
        self.assertEqual(len(set(image_paths)), len(self.EXPECTED_AUTHENTIC_FOODS))

        for food in foods:
            self.assertTrue(bool(food.image), f"Food '{food.name}' has empty image.")
            rel_path = food.image.lstrip('/')
            full_path = os.path.join(settings.BASE_DIR, rel_path.replace('/', os.sep))
            self.assertTrue(os.path.exists(full_path), f"Image file not found on disk: {full_path}")
            self.assertGreater(os.path.getsize(full_path), 50000, f"Image file {full_path} should be an authentic photo.")

    def test_nutritional_values_and_metadata_attached(self):
        """Verifies each item has complete NutritionInfo with calories, macros, and preparation method."""
        foods = FoodItem.objects.filter(name__in=self.EXPECTED_AUTHENTIC_FOODS)
        for food in foods:
            self.assertTrue(hasattr(food, 'nutrition'), f"Item '{food.name}' has no NutritionInfo attached.")
            nutr = food.nutrition
            self.assertGreater(nutr.calories, 0.0, f"Calories must be > 0 for {food.name}")
            self.assertGreater(nutr.protein, 0.0, f"Protein must be > 0 for {food.name}")
            self.assertGreater(nutr.carbohydrates, 0.0, f"Carbohydrates must be > 0 for {food.name}")
            self.assertGreater(nutr.fiber, 0.0, f"Fiber must be > 0 for {food.name}")
            self.assertTrue(bool(nutr.serving_size), f"Serving size missing for {food.name}")
            self.assertTrue(bool(nutr.cooking_method), f"Cooking method missing for {food.name}")
            self.assertTrue(bool(nutr.ingredients), f"Ingredients missing for {food.name}")

    def test_health_suitability_calculation(self):
        """Verifies health prediction engine correctly evaluates nutritional markers."""
        foods = FoodItem.objects.filter(name__in=self.EXPECTED_AUTHENTIC_FOODS)
        for food in foods:
            suit = predict_health_suitability(
                sugar=food.nutrition.total_sugars,
                cholesterol=food.nutrition.cholesterol,
                sodium=food.nutrition.sodium
            )
            self.assertIn('diabetes', suit)
            self.assertIn('cholesterol', suit)
            self.assertIn('bp', suit)

    def test_catalog_view_renders_clean_without_circular_cards(self):
        """Tests that food_catalog view properly renders and contains ZERO circular placeholder cards."""
        resp = self.client.get(reverse('food_catalog'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        
        # Verify none of the removed circular cards appear in the HTML
        for removed_name in self.REMOVED_CIRCULAR_FOODS:
            self.assertNotIn(removed_name, content)
        
        # Verify none of the circular placeholder image filenames appear in the HTML
        for img_name in self.REMOVED_CIRCULAR_IMAGE_FILES:
            self.assertNotIn(img_name, content)

    def test_food_detail_views_load_successfully(self):
        """Verifies each authentic food's detail page loads with 200 OK and renders nutrition facts."""
        foods = FoodItem.objects.filter(name__in=self.EXPECTED_AUTHENTIC_FOODS)
        for food in foods[:5]:
            resp = self.client.get(reverse('food_detail', args=[food.id]))
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode('utf-8')
            self.assertIn(food.name, content)
            self.assertIn(str(food.nutrition.calories), content)
            self.assertIn("Nutritional Facts", content)
