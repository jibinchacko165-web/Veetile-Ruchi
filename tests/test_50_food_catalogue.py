from django.test import TestCase
import os
from django.conf import settings
from food.models import FoodItem, MealSession, Category, NutritionInfo
from food.management.commands.seed_exact_50_catalogue import EXACT_50_FOOD_CATALOGUE

class Exact50FoodCatalogueTests(TestCase):
    """
    Mandatory Test Suite for the Exact 50-Food Health Catalogue:
    - Breakfast: exactly 15 items (1-15)
    - Lunch: exactly 15 items (16-30)
    - Snacks: exactly 10 items (31-40)
    - Dinner: exactly 10 items (41-50)
    - Total: exactly 50 unique items
    - All 50 names, descriptions, categories match the catalogue
    - Zero duplicate names, zero duplicate images
    - Every image file physically exists on disk
    - Complete nutrition metadata attached to every item
    """

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_exact_50_catalogue')

    def test_total_count_is_exactly_50(self):
        total = FoodItem.objects.count()
        self.assertEqual(total, 50, f"Expected exactly 50 food items, found {total}")

    def test_category_and_session_distribution(self):
        breakfast = FoodItem.objects.filter(meal_session__name="Morning Breakfast").count()
        lunch = FoodItem.objects.filter(meal_session__name="Lunch").count()
        snacks = FoodItem.objects.filter(meal_session__name="Evening Snacks").count()
        dinner = FoodItem.objects.filter(meal_session__name="Dinner").count()

        self.assertEqual(breakfast, 15, f"Expected 15 Breakfast items, found {breakfast}")
        self.assertEqual(lunch, 15, f"Expected 15 Lunch items, found {lunch}")
        self.assertEqual(snacks, 10, f"Expected 10 Snacks items, found {snacks}")
        self.assertEqual(dinner, 10, f"Expected 10 Dinner items, found {dinner}")

    def test_all_50_names_match_catalogue(self):
        db_names = set(FoodItem.objects.values_list('name', flat=True))
        expected_names = {item['name'] for item in EXACT_50_FOOD_CATALOGUE}
        missing = expected_names - db_names
        extra = db_names - expected_names

        self.assertEqual(len(missing), 0, f"Missing catalogue items: {missing}")
        self.assertEqual(len(extra), 0, f"Unexpected extra items: {extra}")

    def test_descriptions_and_dietary_classifications(self):
        for expected in EXACT_50_FOOD_CATALOGUE:
            food = FoodItem.objects.get(name=expected['name'])
            self.assertEqual(food.description, expected['description'])
            self.assertEqual(food.meal_session.name, expected['session'])
            self.assertEqual(food.category.name, expected['category'])
            self.assertEqual(food.is_vegetarian, expected['is_veg'])
            self.assertEqual(food.contains_egg, expected['contains_egg'])

    def test_every_item_has_unique_valid_image(self):
        foods = FoodItem.objects.all()
        image_paths = [f.image for f in foods]
        
        # Check uniqueness
        self.assertEqual(len(image_paths), len(set(image_paths)), "Detected duplicate image assignments across items!")

        # Check physical existence on disk
        for food in foods:
            self.assertTrue(bool(food.image), f"Food '{food.name}' has no image assigned")
            rel_path = food.image.lstrip('/media/').lstrip('/')
            full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
            self.assertTrue(
                os.path.exists(full_path),
                f"Image file does not exist on disk for '{food.name}': {full_path}"
            )

    def test_complete_nutrition_metadata(self):
        for food in FoodItem.objects.all():
            self.assertTrue(hasattr(food, 'nutrition'), f"Food '{food.name}' has no nutrition relationship")
            nutr = food.nutrition
            self.assertIsNotNone(nutr, f"Nutrition record is None for '{food.name}'")
            self.assertGreater(nutr.calories, 0, f"Calories missing for '{food.name}'")
            self.assertGreater(nutr.protein, 0, f"Protein missing for '{food.name}'")
            self.assertTrue(bool(nutr.ingredients), f"Ingredients missing for '{food.name}'")
            self.assertTrue(bool(nutr.serving_size), f"Serving size missing for '{food.name}'")
            self.assertTrue(bool(nutr.cooking_method), f"Cooking method missing for '{food.name}'")
