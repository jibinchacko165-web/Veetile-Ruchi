import os
import sys
from django.core.management.base import BaseCommand
from django.db import transaction
from food.models import FoodItem, Category, MealSession, NutritionInfo
from accounts.models import User

# Exact 50-Food Health Catalogue Specification
EXACT_50_FOOD_CATALOGUE = [
    # =========================================================================
    # BREAKFAST — Items 1–15 (15 Items)
    # =========================================================================
    {
        "num": 1,
        "name": "Puttu with Kadala Curry",
        "malayalam_name": "പുട്ടും കടലക്കറിയും",
        "description": "Steamed rice flour cylinders layered with grated coconut, served with a spicy, aromatic black chickpea curry simmered in roasted coconut gravy.",
        "malayalam_description": "പരമ്പരാഗതമായി ആവിയിൽ വേവിച്ച അരിപ്പൊടി പുട്ടും വറുത്തരച്ച കറുത്ത കടലക്കറിയും.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 75.00,
        "image": "/media/food_photos/kerala puttu kadala curry.png",
        "nutrition": {
            "calories": 285.0, "protein": 9.2, "carbohydrates": 51.0, "total_sugars": 2.1,
            "added_sugars": 0.0, "total_fat": 4.8, "saturated_fat": 2.1, "trans_fat": 0.0,
            "fiber": 7.5, "cholesterol": 0.0, "sodium": 240.0,
            "ingredients": "Rice flour, grated coconut, black chickpeas, shallots, ginger, garlic, coriander, turmeric, curry leaves, cold-pressed coconut oil.",
            "allergens": "None", "serving_size": "2 cylindrical pieces puttu + 150ml curry", "cooking_method": "Steamed & boiled"
        }
    },
    {
        "num": 2,
        "name": "Idli with Sambar",
        "malayalam_name": "ഇഡ്ഡലിയും സാമ്പാറും",
        "description": "Soft, steamed fermented rice and black lentil cakes served with a rich, hearty lentil-vegetable stew infused with drumstick and tamarind.",
        "malayalam_description": "ആവിയിൽ വേവിച്ച മൃദുവായ ഇഡ്ഡലിയും നാടൻ പച്ചക്കറി സാമ്പാറും.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 60.00,
        "image": "/media/food_photos/idli_with_sambar.jpg",
        "nutrition": {
            "calories": 210.0, "protein": 7.8, "carbohydrates": 39.5, "total_sugars": 2.4,
            "added_sugars": 0.0, "total_fat": 2.1, "saturated_fat": 0.6, "trans_fat": 0.0,
            "fiber": 5.2, "cholesterol": 0.0, "sodium": 220.0,
            "ingredients": "Parboiled rice, urad dal, toor dal, drumsticks, carrots, shallots, tamarind, fenugreek, mustard seeds, curry leaves.",
            "allergens": "None", "serving_size": "3 pieces idli + 150ml sambar", "cooking_method": "Steamed & simmered"
        }
    },
    {
        "num": 3,
        "name": "Plain Dosa with Sambar",
        "malayalam_name": "നല്ല ദോശയും സാമ്പാറും",
        "description": "Crispy, golden fermented rice and urad dal crepe cooked on a flat griddle, served with aromatic lentil and vegetable sambar.",
        "malayalam_description": "സ്വർണ്ണവർണ്ണത്തിൽ ചുട്ടെടുത്ത മൊരിഞ്ഞ ദോശയും കൊതിയൂറും സാമ്പാറും.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 65.00,
        "image": "/media/food_photos/dosa_with_sambar_and_chutney.jpg",
        "nutrition": {
            "calories": 235.0, "protein": 6.9, "carbohydrates": 42.0, "total_sugars": 2.2,
            "added_sugars": 0.0, "total_fat": 4.5, "saturated_fat": 1.1, "trans_fat": 0.0,
            "fiber": 4.8, "cholesterol": 0.0, "sodium": 250.0,
            "ingredients": "Fermented rice, urad dal, toor dal, mixed vegetables, asafoetida, curry leaves, cold-pressed sesame oil.",
            "allergens": "None", "serving_size": "2 dosas + 150ml sambar", "cooking_method": "Griddled & simmered"
        }
    },
    {
        "num": 4,
        "name": "Appam with Vegetable Stew",
        "malayalam_name": "അപ്പവും വെജിറ്റബിൾ സ്റ്റൂവും",
        "description": "Soft, bowl-shaped fermented rice hoppers with fluffy spongy centers and lacy crisp edges, served with mildly spiced coconut milk vegetable stew.",
        "malayalam_description": "പാലപ്പവും പച്ചക്കറികൾ തേങ്ങാപ്പാലിൽ വേവിച്ച നാടൻ സ്റ്റൂവും.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 80.00,
        "image": "/media/food_photos/Palappam & Vegetable Stew.png",
        "nutrition": {
            "calories": 260.0, "protein": 5.4, "carbohydrates": 46.0, "total_sugars": 3.1,
            "added_sugars": 0.0, "total_fat": 6.8, "saturated_fat": 4.5, "trans_fat": 0.0,
            "fiber": 4.6, "cholesterol": 0.0, "sodium": 190.0,
            "ingredients": "Fermented raw rice, coconut milk, potatoes, carrots, green peas, whole cinnamon, cloves, green chilies.",
            "allergens": "None", "serving_size": "2 appams + 150ml stew", "cooking_method": "Appachatti griddled & simmered"
        }
    },
    {
        "num": 5,
        "name": "Idiyappam with Green Gram Curry",
        "malayalam_name": "ഇടിയപ്പവും ചെറുപയർ കറിയും",
        "description": "Delicate steamed rice string hoppers served with protein-packed whole green gram (cherupayar) curry cooked with shallots, coconut, and spices.",
        "malayalam_description": "നൂൽപ്പുട്ടും ചെറുപയർ നാടൻ തേങ്ങ ചേർത്തുണ്ടാക്കിയ കറിയും.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 75.00,
        "image": "/media/food_photos/idiyappam_with_vegetable_curry.jpg",
        "nutrition": {
            "calories": 245.0, "protein": 8.6, "carbohydrates": 45.0, "total_sugars": 1.9,
            "added_sugars": 0.0, "total_fat": 3.6, "saturated_fat": 1.8, "trans_fat": 0.0,
            "fiber": 6.8, "cholesterol": 0.0, "sodium": 205.0,
            "ingredients": "Rice flour, grated coconut, whole green gram, shallots, garlic, turmeric, mustard, curry leaves.",
            "allergens": "None", "serving_size": "3 pieces idiyappam + 150ml curry", "cooking_method": "Steamed & boiled"
        }
    },
    {
        "num": 6,
        "name": "Wheat Puttu with Green Gram Curry",
        "malayalam_name": "ഗോതമ്പ് പുട്ടും ചെറുപയർ കറിയും",
        "description": "Nutritious roasted whole-wheat flour steamed with fresh coconut layers, accompanied by mildly spiced steamed green gram curry.",
        "malayalam_description": "ആരോഗ്യകരമായ വറുത്ത ഗോതമ്പ് പൊടി പുട്ടും ചെറുപയർ കറിയും.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 75.00,
        "image": "/media/food_photos/new/breakfast/wheat_puttu_with_kadala_curry.jpg",
        "nutrition": {
            "calories": 265.0, "protein": 9.8, "carbohydrates": 47.0, "total_sugars": 1.8,
            "added_sugars": 0.0, "total_fat": 3.8, "saturated_fat": 1.9, "trans_fat": 0.0,
            "fiber": 8.4, "cholesterol": 0.0, "sodium": 195.0,
            "ingredients": "Whole-wheat flour, fresh coconut, whole green gram, ginger, green chilies, shallots, curry leaves.",
            "allergens": "Wheat (Gluten)", "serving_size": "2 pcs puttu + 150ml curry", "cooking_method": "Steamed & boiled"
        }
    },
    {
        "num": 7,
        "name": "Ragi Dosa with Sambar",
        "malayalam_name": "റാഗി ദോശയും സാമ്പാറും",
        "description": "Healthy, fiber-rich finger millet (ragi) savory crepes packed with calcium, served with hot Kerala vegetable sambar.",
        "malayalam_description": "കാൽസ്യവും നാരുകളും സമൃദ്ധമായ റാഗി ദോശയും സാമ്പാറും.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 70.00,
        "image": "/media/food_photos/new/dinner/ragi_dosa_with_vegetable_sambar.jpg",
        "nutrition": {
            "calories": 215.0, "protein": 6.8, "carbohydrates": 40.5, "total_sugars": 2.0,
            "added_sugars": 0.0, "total_fat": 3.2, "saturated_fat": 0.7, "trans_fat": 0.0,
            "fiber": 7.2, "cholesterol": 0.0, "sodium": 210.0,
            "ingredients": "Whole finger millet (ragi), urad dal, toor dal, mixed country vegetables, turmeric, cumin.",
            "allergens": "None", "serving_size": "2 dosas + 150ml sambar", "cooking_method": "Tawa griddled"
        }
    },
    {
        "num": 8,
        "name": "Green Gram Dosa",
        "malayalam_name": "ചെറുപയർ ദോശ (പെസരട്ട്)",
        "description": "Wholesome, protein-rich batter made of whole soaked green gram and ginger, griddled into crisp savory crepes (Pesarattu style).",
        "malayalam_description": "മുഴുവൻ ചെറുപയറും ഇഞ്ചിയും അരച്ചുണ്ടാക്കിയ സ്വാദിഷ്ടമായ പെസരട്ട് ദോശ.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 70.00,
        "image": "/media/food_photos/new/breakfast/cherupayar_dosa_pesarattu.jpg",
        "nutrition": {
            "calories": 220.0, "protein": 11.2, "carbohydrates": 36.0, "total_sugars": 1.4,
            "added_sugars": 0.0, "total_fat": 3.5, "saturated_fat": 0.8, "trans_fat": 0.0,
            "fiber": 6.5, "cholesterol": 0.0, "sodium": 185.0,
            "ingredients": "Whole green gram, ginger, green chilies, cumin seeds, shallots, cold-pressed oil.",
            "allergens": "None", "serving_size": "2 dosas", "cooking_method": "Tawa griddled"
        }
    },
    {
        "num": 9,
        "name": "Vegetable Oats Upma",
        "malayalam_name": "വെജിറ്റബിൾ ഓട്സ് ഉപ്പുമാവ്",
        "description": "Whole rolled oats roasted and gently simmered with finely chopped carrots, green beans, ginger, mustard seeds, and fresh curry leaves.",
        "malayalam_description": "കാരറ്റും ബീൻസും ചേർത്ത ആരോഗ്യപ്രദമായ ഓട്സ് ഉപ്പുമാവ്.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 65.00,
        "image": "/media/food_photos/new/breakfast/oats_vegetable_upma.jpg",
        "nutrition": {
            "calories": 185.0, "protein": 6.2, "carbohydrates": 31.0, "total_sugars": 1.5,
            "added_sugars": 0.0, "total_fat": 4.0, "saturated_fat": 0.8, "trans_fat": 0.0,
            "fiber": 5.8, "cholesterol": 0.0, "sodium": 180.0,
            "ingredients": "Rolled oats, carrots, french beans, green chillies, ginger, mustard seeds, curry leaves, cold-pressed coconut oil.",
            "allergens": "Oats", "serving_size": "1 bowl (200g)", "cooking_method": "Sautéed & steamed"
        }
    },
    {
        "num": 10,
        "name": "Vegetable Aval Upma",
        "malayalam_name": "അവൽ വെജിറ്റബിൾ ഉപ്പുമാവ്",
        "description": "Traditional Kerala flattened rice (poha/aval) tempered with mustard, green chilies, grated ginger, and mixed garden vegetables.",
        "malayalam_description": "പച്ചക്കറികളും കടുക് വറവുമിട്ട നാടൻ തവിടുള്ള അവൽ ഉപ്പുമാവ്.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 60.00,
        "image": "/media/food_photos/vegetable_aval_upma.jpg",
        "nutrition": {
            "calories": 195.0, "protein": 4.5, "carbohydrates": 38.0, "total_sugars": 1.6,
            "added_sugars": 0.0, "total_fat": 3.1, "saturated_fat": 1.2, "trans_fat": 0.0,
            "fiber": 4.2, "cholesterol": 0.0, "sodium": 175.0,
            "ingredients": "Red rice flattened flakes (aval), carrots, green peas, shallots, ginger, mustard seeds, curry leaves.",
            "allergens": "None", "serving_size": "1 bowl (200g)", "cooking_method": "Tempered & sautéed"
        }
    },
    {
        "num": 11,
        "name": "Broken Wheat Upma",
        "malayalam_name": "നുറുക്ക് ഗോതമ്പ് ഉപ്പുമാവ്",
        "description": "Fiber-rich cracked wheat (nurukku gothambu) simmered with vegetables, shallots, and curry leaves for a slow-digesting, healthy breakfast.",
        "malayalam_description": "നുറുക്ക് ഗോതമ്പും പച്ചക്കറികളും ചേർത്ത പോഷകസമൃദ്ധമായ ഉപ്പുമാവ്.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 65.00,
        "image": "/media/food_photos/new/breakfast/broken_wheat_upma.jpg",
        "nutrition": {
            "calories": 205.0, "protein": 6.8, "carbohydrates": 39.0, "total_sugars": 1.4,
            "added_sugars": 0.0, "total_fat": 2.8, "saturated_fat": 0.6, "trans_fat": 0.0,
            "fiber": 7.8, "cholesterol": 0.0, "sodium": 185.0,
            "ingredients": "Broken wheat (dalia), carrots, beans, green chilies, ginger, mustard seeds, curry leaves.",
            "allergens": "Wheat (Gluten)", "serving_size": "1 bowl (220g)", "cooking_method": "Simmered"
        }
    },
    {
        "num": 12,
        "name": "Green Gram Rice Porridge",
        "malayalam_name": "ചെറുപയർ കഞ്ഞി",
        "description": "Comforting, nutrient-dense Kerala kanji made with whole green gram, red matta rice, and a splash of light coconut milk.",
        "malayalam_description": "കുത്തരിയും ചെറുപയറും ചേർത്തുണ്ടാക്കിയ ആരോഗ്യകരമായ കഞ്ഞി.",
        "session": "Morning Breakfast",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 60.00,
        "image": "/media/food_photos/new/dinner/matta_rice_kanji_green_gram.jpg",
        "nutrition": {
            "calories": 210.0, "protein": 8.2, "carbohydrates": 41.0, "total_sugars": 1.2,
            "added_sugars": 0.0, "total_fat": 2.0, "saturated_fat": 1.0, "trans_fat": 0.0,
            "fiber": 6.0, "cholesterol": 0.0, "sodium": 160.0,
            "ingredients": "Kerala matta rice, whole green gram (cherupayar), grated coconut, cumin seeds, shallots.",
            "allergens": "None", "serving_size": "1 large bowl (300ml)", "cooking_method": "Boiled & simmered"
        }
    },
    {
        "num": 13,
        "name": "Egg Roast with Whole-Wheat Chapati",
        "malayalam_name": "മുട്ട റോസ്റ്റും ഗോതമ്പ് ചപ്പാത്തിയും",
        "description": "Soft whole-wheat flatbreads served with hard-boiled eggs sautéed in a thick, spiced onion, tomato, and crushed black pepper gravy.",
        "malayalam_description": "തനി നാടൻ മുട്ട റോസ്റ്റും മൃദുവായ ഗോതമ്പ് ചപ്പാത്തിയും.",
        "session": "Morning Breakfast",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": True,
        "price": 90.00,
        "image": "/media/food_photos/new/dinner/chapati_with_egg_bhurji.jpg",
        "nutrition": {
            "calories": 320.0, "protein": 14.5, "carbohydrates": 38.0, "total_sugars": 2.8,
            "added_sugars": 0.0, "total_fat": 11.2, "saturated_fat": 2.8, "trans_fat": 0.0,
            "fiber": 5.4, "cholesterol": 185.0, "sodium": 310.0,
            "ingredients": "Whole-wheat flour, eggs, shallots, tomatoes, ginger, garlic, fennel, black pepper, curry leaves.",
            "allergens": "Eggs, Wheat (Gluten)", "serving_size": "2 chapatis + 1 egg roast", "cooking_method": "Griddled & sautéed"
        }
    },
    {
        "num": 14,
        "name": "Vegetable Omelette with Whole-Wheat Toast",
        "malayalam_name": "വെജിറ്റബിൾ ഓംലെറ്റും ഗോതമ്പ് ടോസ്റ്റും",
        "description": "Fluffy country-egg omelette folded with chopped onions, tomatoes, and green herbs, served with toasted whole-wheat bread slices.",
        "malayalam_description": "പച്ചക്കറികൾ ചേർത്ത മുട്ട ഓംലെറ്റും ബ്രൗൺ ബ്രെഡ് ടോസ്റ്റും.",
        "session": "Morning Breakfast",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": True,
        "price": 85.00,
        "image": "/media/food_photos/vegetable_omelette_toast.jpg",
        "nutrition": {
            "calories": 280.0, "protein": 13.8, "carbohydrates": 26.0, "total_sugars": 2.0,
            "added_sugars": 0.0, "total_fat": 12.5, "saturated_fat": 3.2, "trans_fat": 0.0,
            "fiber": 4.1, "cholesterol": 190.0, "sodium": 290.0,
            "ingredients": "Eggs, onions, tomatoes, green chilies, coriander leaves, whole-wheat bread slices, olive oil.",
            "allergens": "Eggs, Wheat (Gluten)", "serving_size": "1 omelette (2 eggs) + 2 toasts", "cooking_method": "Pan-seared & toasted"
        }
    },
    {
        "num": 15,
        "name": "Idiyappam with Light Chicken Stew",
        "malayalam_name": "ഇടിയപ്പവും ചിക്കൻ സ്റ്റൂവും",
        "description": "Soft steamed string hoppers served with a gentle, fragrant chicken and potato stew simmered in light coconut milk, cinnamon, and cloves.",
        "malayalam_description": "നൂൽപ്പുട്ടും നേർത്ത തേങ്ങാപ്പാലിൽ തയ്യാറാക്കിയ ചിക്കൻ സ്റ്റൂവും.",
        "session": "Morning Breakfast",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 110.00,
        "image": "/media/food_photos/idiyappam_with_chicken_curry.jpg",
        "nutrition": {
            "calories": 315.0, "protein": 18.2, "carbohydrates": 39.0, "total_sugars": 2.2,
            "added_sugars": 0.0, "total_fat": 8.5, "saturated_fat": 4.8, "trans_fat": 0.0,
            "fiber": 3.5, "cholesterol": 42.0, "sodium": 280.0,
            "ingredients": "Rice flour, skinless chicken breast, light coconut milk, potatoes, carrots, cinnamon, cloves, green chilies.",
            "allergens": "None", "serving_size": "3 idiyappam + 150ml stew", "cooking_method": "Steamed & stewed"
        }
    },

    # =========================================================================
    # LUNCH — Items 16–30 (15 Items)
    # =========================================================================
    {
        "num": 16,
        "name": "Matta Rice with Avial and Thoran",
        "malayalam_name": "മട്ടയരി ചോറും അവിയലും തോരനും",
        "description": "Authentic Kerala red matta rice served with traditional avial (mixed vegetables in curd-coconut paste) and seasonal vegetable thoran.",
        "malayalam_description": "കുത്തരി ചോറും സ്വാദിഷ്ടമായ അവിയലും പച്ചക്കറി തോരനും.",
        "session": "Lunch",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": False,
        "contains_egg": False,
        "price": 95.00,
        "image": "/media/food_photos/new/lunch/kerala_vegetable_avial_brown_rice.jpg",
        "nutrition": {
            "calories": 360.0, "protein": 7.8, "carbohydrates": 64.0, "total_sugars": 3.5,
            "added_sugars": 0.0, "total_fat": 7.8, "saturated_fat": 5.2, "trans_fat": 0.0,
            "fiber": 8.2, "cholesterol": 2.0, "sodium": 240.0,
            "ingredients": "Kerala matta rice, ash gourd, raw plantain, yam, drumstick, coconut, curd, cabbage, green chilies, curry leaves.",
            "allergens": "Dairy (Curd)", "serving_size": "1 meal plate (250g rice + 100g avial + 60g thoran)", "cooking_method": "Boiled & steamed"
        }
    },
    {
        "num": 17,
        "name": "Matta Rice with Moru Curry",
        "malayalam_name": "മട്ടയരി ചോറും കാച്ചിയ മോരും",
        "description": "Steamed Kerala red rice served with seasoned buttermilk curry (kachiya moru) tempered with mustard seeds, fenugreek, and ginger.",
        "malayalam_description": "കുത്തരി ചോറും ഇഞ്ചിയും വെളുത്തുള്ളിയും ചേർത്ത കാച്ചിയ മോരുകറിയും.",
        "session": "Lunch",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": False,
        "contains_egg": False,
        "price": 85.00,
        "image": "/media/food_photos/new/lunch/matta_rice_kumbalanga_moru.jpg",
        "nutrition": {
            "calories": 310.0, "protein": 6.8, "carbohydrates": 58.0, "total_sugars": 3.0,
            "added_sugars": 0.0, "total_fat": 4.5, "saturated_fat": 2.5, "trans_fat": 0.0,
            "fiber": 5.5, "cholesterol": 6.0, "sodium": 210.0,
            "ingredients": "Kerala matta rice, churned buttermilk, shallots, ginger, garlic, turmeric, mustard, fenugreek seeds, curry leaves.",
            "allergens": "Dairy (Buttermilk)", "serving_size": "1 meal plate (250g rice + 150ml moru)", "cooking_method": "Boiled & tempered"
        }
    },
    {
        "num": 18,
        "name": "Matta Rice with Parippu Curry",
        "malayalam_name": "മട്ടയരി ചോറും നാടൻ പരിപ്പുകറിയും",
        "description": "Nutritious red matta rice served with smooth moong dal curry cooked with ground coconut, cumin, and fragrant curry leaves.",
        "malayalam_description": "കുത്തരി ചോറും തേങ്ങയരച്ച നാടൻ ചെറുപയർ പരിപ്പുകറിയും.",
        "session": "Lunch",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 85.00,
        "image": "/media/food_photos/kerala_meals_with_parippu_curry.jpg",
        "nutrition": {
            "calories": 340.0, "protein": 10.5, "carbohydrates": 62.0, "total_sugars": 1.8,
            "added_sugars": 0.0, "total_fat": 5.2, "saturated_fat": 3.2, "trans_fat": 0.0,
            "fiber": 7.0, "cholesterol": 0.0, "sodium": 195.0,
            "ingredients": "Kerala matta rice, yellow moong dal, grated coconut, cumin seeds, garlic, green chilies, curry leaves.",
            "allergens": "None", "serving_size": "1 meal plate (250g rice + 150ml parippu)", "cooking_method": "Boiled & simmered"
        }
    },
    {
        "num": 19,
        "name": "Vegetable Sambar Rice",
        "malayalam_name": "സാമ്പാർ സാദം (വെജിറ്റബിൾ സാമ്പാർ ചോറ്)",
        "description": "Hearty one-pot meal combining cooked rice with spicy lentil broth, ash gourd, drumsticks, and freshly ground sambar spices.",
        "malayalam_description": "പച്ചക്കറികളും പരിപ്പും ചേർത്തുണ്ടാക്കിയ സാമ്പാർ ചോറ്.",
        "session": "Lunch",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 90.00,
        "image": "/media/food_photos/vegetable_sambar_rice.jpg",
        "nutrition": {
            "calories": 330.0, "protein": 9.4, "carbohydrates": 60.0, "total_sugars": 2.8,
            "added_sugars": 0.0, "total_fat": 4.8, "saturated_fat": 1.2, "trans_fat": 0.0,
            "fiber": 7.2, "cholesterol": 0.0, "sodium": 260.0,
            "ingredients": "Rice, toor dal, drumsticks, ash gourd, carrots, shallots, tamarind, roasted coriander, fenugreek, curry leaves.",
            "allergens": "None", "serving_size": "1 bowl (350g)", "cooking_method": "One-pot simmered"
        }
    },
    {
        "num": 20,
        "name": "Brown Rice with Chickpea Curry",
        "malayalam_name": "ബ്രൗൺ റൈസും വെള്ളക്കടല കറിയും",
        "description": "Fiber-rich whole brown rice served with tender white chickpeas simmered in an aromatic tomato-onion gravy.",
        "malayalam_description": "തവിടോടുകൂടിയ ബ്രൗൺ റൈസും പ്രോട്ടീൻ നിറഞ്ഞ വെള്ളക്കടല കറിയും.",
        "session": "Lunch",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 95.00,
        "image": "/media/food_photos/brown_rice_with_chickpea_curry.jpg",
        "nutrition": {
            "calories": 350.0, "protein": 11.8, "carbohydrates": 62.0, "total_sugars": 2.5,
            "added_sugars": 0.0, "total_fat": 5.4, "saturated_fat": 1.0, "trans_fat": 0.0,
            "fiber": 9.5, "cholesterol": 0.0, "sodium": 230.0,
            "ingredients": "Whole brown rice, kabuli chickpeas, tomatoes, onions, ginger, garlic, garam masala, fresh cilantro.",
            "allergens": "None", "serving_size": "1 meal plate (250g rice + 150ml curry)", "cooking_method": "Boiled & simmered"
        }
    },
    {
        "num": 21,
        "name": "Matta Rice with Green Gram Curry",
        "malayalam_name": "മട്ടയരി ചോറും ചെറുപയർ കറിയും",
        "description": "Wholesome red matta rice paired with stewed whole green gram curry, crushed shallots, and fresh curry leaves.",
        "malayalam_description": "കുത്തരി ചോറും പ്രോട്ടീൻ നിറഞ്ഞ ചെറുപയർ കൂട്ടുകറിയും.",
        "session": "Lunch",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 85.00,
        "image": "/media/food_photos/new/lunch/brown_rice_cherupayar_parippu.jpg",
        "nutrition": {
            "calories": 335.0, "protein": 10.2, "carbohydrates": 61.0, "total_sugars": 1.8,
            "added_sugars": 0.0, "total_fat": 4.2, "saturated_fat": 1.5, "trans_fat": 0.0,
            "fiber": 8.0, "cholesterol": 0.0, "sodium": 190.0,
            "ingredients": "Kerala matta rice, whole green gram, shallots, garlic, turmeric, coconut oil, curry leaves.",
            "allergens": "None", "serving_size": "1 meal plate (250g rice + 150ml curry)", "cooking_method": "Boiled & stewed"
        }
    },
    {
        "num": 22,
        "name": "Matta Rice with Black Chickpea Curry",
        "malayalam_name": "മട്ടയരി ചോറും കടലക്കറിയും",
        "description": "Steamed matta rice accompanied by traditional Kerala kadala curry made with black chickpeas and roasted coconut gravy.",
        "malayalam_description": "കുത്തരി ചോറും വറുത്തരച്ച കറുത്ത കടലക്കറിയും.",
        "session": "Lunch",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 90.00,
        "image": "/media/food_photos/new/lunch/matta_rice_erissery.jpg",
        "nutrition": {
            "calories": 355.0, "protein": 10.8, "carbohydrates": 63.0, "total_sugars": 2.0,
            "added_sugars": 0.0, "total_fat": 5.8, "saturated_fat": 2.8, "trans_fat": 0.0,
            "fiber": 9.0, "cholesterol": 0.0, "sodium": 225.0,
            "ingredients": "Kerala matta rice, black chickpeas, roasted coconut paste, shallots, ginger, coriander, fennel.",
            "allergens": "None", "serving_size": "1 meal plate (250g rice + 150ml curry)", "cooking_method": "Boiled & simmered"
        }
    },
    {
        "num": 23,
        "name": "Matta Rice with Sardine Curry",
        "malayalam_name": "മട്ടയരി ചോറും മത്തി മുളകിട്ടതും",
        "description": "Fresh coastal sardines (mathi) cooked in a tangy red chili, shallot, and Malabar tamarind (kudampuli) curry, served with matta rice.",
        "malayalam_description": "കുത്തരി ചോറും കുടംപുളിയിട്ട് വറ്റിച്ച മത്തിക്കറിയും.",
        "session": "Lunch",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 120.00,
        "image": "/media/food_photos/new/lunch/mathi_sardine_mulakittathu.jpg",
        "nutrition": {
            "calories": 375.0, "protein": 22.5, "carbohydrates": 54.0, "total_sugars": 1.5,
            "added_sugars": 0.0, "total_fat": 8.8, "saturated_fat": 2.2, "trans_fat": 0.0,
            "fiber": 5.6, "cholesterol": 55.0, "sodium": 290.0,
            "ingredients": "Kerala matta rice, fresh sardines (mathi), Malabar tamarind (kudampuli), Kashmiri chili, fenugreek, shallots, curry leaves.",
            "allergens": "Fish", "serving_size": "1 meal plate (250g rice + 2 fish + curry)", "cooking_method": "Earthen pot simmered"
        }
    },
    {
        "num": 24,
        "name": "Matta Rice with Grilled Fish",
        "malayalam_name": "മട്ടയരി ചോറും അയില പൊള്ളിച്ചതും",
        "description": "Steamed unpolished red rice paired with shallow pan-grilled fresh fish marinated in turmeric, crushed chili, and lemon juice.",
        "malayalam_description": "കുത്തരി ചോറും കുരുമുളകും മഞ്ഞളും പുരട്ടി പൊള്ളിച്ച മീനും.",
        "session": "Lunch",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 140.00,
        "image": "/media/food_photos/new/lunch/grilled_ayakoora_vegetables.jpg",
        "nutrition": {
            "calories": 390.0, "protein": 26.0, "carbohydrates": 52.0, "total_sugars": 1.2,
            "added_sugars": 0.0, "total_fat": 8.0, "saturated_fat": 1.8, "trans_fat": 0.0,
            "fiber": 5.2, "cholesterol": 60.0, "sodium": 270.0,
            "ingredients": "Matta rice, fresh seer fish/mackerel fillet, turmeric powder, black pepper, lemon juice, curry leaves.",
            "allergens": "Fish", "serving_size": "1 meal plate (250g rice + 1 grilled fillet)", "cooking_method": "Steamed & pan-grilled"
        }
    },
    {
        "num": 25,
        "name": "Kerala Fish Curry Meal",
        "malayalam_name": "കേരള ഫിഷ് കറി ഊണ്",
        "description": "Traditional Kerala lunch thali featuring matta rice, spicy nadan fish curry, vegetable thoran, moru, and crispy poppadom.",
        "malayalam_description": "കുത്തരി ചോറും നാടൻ മീൻകറിയും തോരനും മോരും കൂട്ടിയുള്ള ഉച്ചയൂണ്.",
        "session": "Lunch",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 135.00,
        "image": "/media/food_photos/kerala_fish_curry_meals.jpg",
        "nutrition": {
            "calories": 420.0, "protein": 24.0, "carbohydrates": 62.0, "total_sugars": 2.5,
            "added_sugars": 0.0, "total_fat": 9.5, "saturated_fat": 3.8, "trans_fat": 0.0,
            "fiber": 6.8, "cholesterol": 50.0, "sodium": 320.0,
            "ingredients": "Matta rice, kingfish/ayala, kudampuli, coconut, cabbage thoran, seasoned buttermilk, ginger, shallots.",
            "allergens": "Fish, Dairy", "serving_size": "Complete Thali Meal", "cooking_method": "Traditional boiled & curried"
        }
    },
    {
        "num": 26,
        "name": "Matta Rice with Light Chicken Curry",
        "malayalam_name": "മട്ടയരി ചോറും നാടൻ ചിക്കൻ കറിയും",
        "description": "Tender chicken pieces simmered in a mildly spiced coriander and shallot sauce, served over wholesome red matta rice.",
        "malayalam_description": "കുത്തരി ചോറും മല്ലിയും ചെറിയുള്ളിയും ചേർത്ത നാടൻ ചിക്കൻ കറിയും.",
        "session": "Lunch",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 130.00,
        "image": "/media/food_photos/new/lunch/kerala_herb_grilled_chicken.jpg",
        "nutrition": {
            "calories": 410.0, "protein": 25.5, "carbohydrates": 55.0, "total_sugars": 1.9,
            "added_sugars": 0.0, "total_fat": 9.0, "saturated_fat": 2.4, "trans_fat": 0.0,
            "fiber": 5.4, "cholesterol": 65.0, "sodium": 310.0,
            "ingredients": "Kerala matta rice, skinless chicken breast/thigh, shallots, garlic, tomatoes, coriander, fennel seeds, curry leaves.",
            "allergens": "None", "serving_size": "1 meal plate (250g rice + 180ml chicken curry)", "cooking_method": "Boiled & simmered"
        }
    },
    {
        "num": 27,
        "name": "Matta Rice with Chicken Pepper Roast",
        "malayalam_name": "മട്ടയരി ചോറും ചിക്കൻ പെപ്പർ റോസ്റ്റും",
        "description": "Spicy and aromatic chicken pieces dry-roasted with freshly crushed Malabar black pepper, garlic, and curry leaves, served with matta rice.",
        "malayalam_description": "കുത്തരി ചോറും കുരുമുളകിട്ട് വരട്ടിയ ചിക്കൻ റോസ്റ്റും.",
        "session": "Lunch",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 140.00,
        "image": "/media/food_photos/rice_with_chicken_fry.jpg",
        "nutrition": {
            "calories": 435.0, "protein": 27.2, "carbohydrates": 54.0, "total_sugars": 1.6,
            "added_sugars": 0.0, "total_fat": 11.0, "saturated_fat": 2.8, "trans_fat": 0.0,
            "fiber": 5.5, "cholesterol": 70.0, "sodium": 330.0,
            "ingredients": "Matta rice, chicken pieces, crushed Malabar black pepper, garlic, shallots, fennel, coconut slices, curry leaves.",
            "allergens": "None", "serving_size": "1 meal plate (250g rice + 120g chicken roast)", "cooking_method": "Pan-roasted"
        }
    },
    {
        "num": 28,
        "name": "Matta Rice with Egg Curry",
        "malayalam_name": "മട്ടയരി ചോറും മുട്ടക്കറിയും",
        "description": "Hard-boiled eggs cooked in a flavorful Kerala coconut and roasted onion gravy, served over steaming hot red rice.",
        "malayalam_description": "കുത്തരി ചോറും നാടൻ തേങ്ങാപ്പാൽ ചേർത്ത മുട്ടക്കറിയും.",
        "session": "Lunch",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": True,
        "price": 100.00,
        "image": "/media/food_photos/appam_egg_curry.png",
        "nutrition": {
            "calories": 370.0, "protein": 14.8, "carbohydrates": 56.0, "total_sugars": 2.2,
            "added_sugars": 0.0, "total_fat": 9.5, "saturated_fat": 3.4, "trans_fat": 0.0,
            "fiber": 5.4, "cholesterol": 185.0, "sodium": 280.0,
            "ingredients": "Kerala matta rice, farm eggs, onions, tomatoes, light coconut milk, ginger, fennel, curry leaves.",
            "allergens": "Eggs", "serving_size": "1 meal plate (250g rice + 2 eggs in curry)", "cooking_method": "Boiled & simmered"
        }
    },
    {
        "num": 29,
        "name": "Matta Rice with Olan and Avial",
        "malayalam_name": "മട്ടയരി ചോറും ഓലനും അവിയലും",
        "description": "Delicate ash gourd and red cowpea olan simmered in thin coconut milk, paired with traditional vegetable avial and matta rice.",
        "malayalam_description": "കുത്തരി ചോറും കുമ്പളങ്ങ ഓലനും കൂട്ടുകറി അവിയലും.",
        "session": "Lunch",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": False,
        "contains_egg": False,
        "price": 100.00,
        "image": "/media/food_photos/new/lunch/matta_rice_olan_beetroot_thoran.jpg",
        "nutrition": {
            "calories": 345.0, "protein": 8.2, "carbohydrates": 62.0, "total_sugars": 3.2,
            "added_sugars": 0.0, "total_fat": 7.0, "saturated_fat": 4.8, "trans_fat": 0.0,
            "fiber": 8.5, "cholesterol": 2.0, "sodium": 210.0,
            "ingredients": "Kerala matta rice, ash gourd, red cowpeas (vanpayar), coconut milk, mixed country vegetables, raw coconut oil.",
            "allergens": "Dairy (Avial curd)", "serving_size": "1 meal plate (250g rice + olan + avial)", "cooking_method": "Simmered & steamed"
        }
    },
    {
        "num": 30,
        "name": "Vegetable Millet and Lentil Bowl",
        "malayalam_name": "മില്ലറ്റ് പരിപ്പ് ഹെൽത്തി ബൗൾ",
        "description": "Modern healthy fusion bowl of foxtail millet, simmered lentils, steamed greens, and roasted cumin dressing.",
        "malayalam_description": "തിന മില്ലറ്റും പരിപ്പും നാടൻ ചീരയും ചേർത്ത സമീകൃത ആഹാരം.",
        "session": "Lunch",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 105.00,
        "image": "/media/food_photos/new/lunch/millet_sadya_meal_pulissery.jpg",
        "nutrition": {
            "calories": 310.0, "protein": 11.5, "carbohydrates": 54.0, "total_sugars": 1.5,
            "added_sugars": 0.0, "total_fat": 4.5, "saturated_fat": 0.9, "trans_fat": 0.0,
            "fiber": 9.2, "cholesterol": 0.0, "sodium": 180.0,
            "ingredients": "Foxtail millet (thina), yellow lentils, steamed spinach (cheera), carrots, cumin, lemon juice.",
            "allergens": "None", "serving_size": "1 bowl (300g)", "cooking_method": "Steamed & tossed"
        }
    },

    # =========================================================================
    # SNACKS — Items 31–40 (10 Items)
    # =========================================================================
    {
        "num": 31,
        "name": "Steamed Kozhukatta",
        "malayalam_name": "ആവിയിൽ വേവിച്ച കൊഴുക്കട്ട",
        "description": "Healthy steamed rice dumplings stuffed with fresh grated coconut and a hint of cardamom-infused jaggery.",
        "malayalam_description": "തേങ്ങയും ശർക്കരയും ചേർത്ത ആവിയിൽ പുഴുങ്ങിയ കൊഴുക്കട്ട.",
        "session": "Evening Snacks",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 40.00,
        "image": "/media/food_photos/kozhukatta.jpg",
        "nutrition": {
            "calories": 160.0, "protein": 2.8, "carbohydrates": 32.0, "total_sugars": 7.5,
            "added_sugars": 5.0, "total_fat": 2.5, "saturated_fat": 1.8, "trans_fat": 0.0,
            "fiber": 2.1, "cholesterol": 0.0, "sodium": 45.0,
            "ingredients": "Rice flour, fresh grated coconut, organic jaggery, cardamom powder, pinch of salt.",
            "allergens": "None", "serving_size": "2 pieces (120g)", "cooking_method": "Steamed"
        }
    },
    {
        "num": 32,
        "name": "Ela Ada",
        "malayalam_name": "നാടൻ ഇലയട",
        "description": "Classic Kerala delicacy of rice parcels filled with sweet coconut and jaggery, steamed inside fragrant banana leaves.",
        "malayalam_description": "വാഴയിലയിൽ പൊതിഞ്ഞ് ആവിയിൽ വേവിച്ച തേങ്ങ-ശർക്കര ഇലയട.",
        "session": "Evening Snacks",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 45.00,
        "image": "/media/food_photos/Steamed Ela Ada (Jaggery & Coconut in Banana Leaf).png",
        "nutrition": {
            "calories": 175.0, "protein": 3.0, "carbohydrates": 34.0, "total_sugars": 8.0,
            "added_sugars": 5.5, "total_fat": 2.9, "saturated_fat": 2.0, "trans_fat": 0.0,
            "fiber": 2.5, "cholesterol": 0.0, "sodium": 50.0,
            "ingredients": "Roasted rice flour, fresh coconut, jaggery syrup, cardamom, fresh banana leaf wrap.",
            "allergens": "None", "serving_size": "2 adas (140g)", "cooking_method": "Banana-leaf steamed"
        }
    },
    {
        "num": 33,
        "name": "Roasted Black Chickpeas",
        "malayalam_name": "വറുത്ത കറുത്ത കടല",
        "description": "Crunchy, dry-roasted black chickpeas seasoned with mild salt and crushed black pepper for a high-protein afternoon snack.",
        "malayalam_description": "എണ്ണയില്ലാതെ വറുത്തെടുത്ത പ്രോട്ടീൻ നിറഞ്ഞ കടല.",
        "session": "Evening Snacks",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 35.00,
        "image": "/media/food_photos/new/snacks/dry_roasted_chana_snack.jpg",
        "nutrition": {
            "calories": 150.0, "protein": 7.5, "carbohydrates": 24.0, "total_sugars": 1.2,
            "added_sugars": 0.0, "total_fat": 2.2, "saturated_fat": 0.4, "trans_fat": 0.0,
            "fiber": 5.5, "cholesterol": 0.0, "sodium": 120.0,
            "ingredients": "Whole black chickpeas (desi chana), black pepper, rock salt, turmeric.",
            "allergens": "None", "serving_size": "1 bowl (60g)", "cooking_method": "Dry-roasted"
        }
    },
    {
        "num": 34,
        "name": "Green Gram Sundal",
        "malayalam_name": "ചെറുപയർ ചുണ്ടൽ",
        "description": "Steamed whole green gram tossed with mustard seeds, curry leaves, ginger, and freshly grated coconut.",
        "malayalam_description": "തേങ്ങാപ്പൂളും കടുകും കറിവേപ്പിലയും താളിച്ച ചെറുപയർ ചുണ്ടൽ.",
        "session": "Evening Snacks",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 40.00,
        "image": "/media/food_photos/new/snacks/steamed_cherupayar_sundal.jpg",
        "nutrition": {
            "calories": 140.0, "protein": 7.2, "carbohydrates": 22.0, "total_sugars": 1.0,
            "added_sugars": 0.0, "total_fat": 2.5, "saturated_fat": 1.2, "trans_fat": 0.0,
            "fiber": 5.0, "cholesterol": 0.0, "sodium": 110.0,
            "ingredients": "Whole green gram, grated coconut, mustard seeds, green chilies, ginger, curry leaves.",
            "allergens": "None", "serving_size": "1 bowl (120g)", "cooking_method": "Steamed & tossed"
        }
    },
    {
        "num": 35,
        "name": "Steamed Sweet Potato",
        "malayalam_name": "പുഴുങ്ങിയ മധുരക്കിഴങ്ങ്",
        "description": "Naturally sweet, vitamin-rich sweet potato slices gently steamed to perfection with a light pinch of sea salt.",
        "malayalam_description": "ആവിയിൽ പുഴുങ്ങിയ നാടൻ മധുരക്കിഴങ്ങ്.",
        "session": "Evening Snacks",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 40.00,
        "image": "/media/food_photos/new/snacks/sweet_potato_steamed_slices.jpg",
        "nutrition": {
            "calories": 130.0, "protein": 2.2, "carbohydrates": 30.0, "total_sugars": 6.2,
            "added_sugars": 0.0, "total_fat": 0.2, "saturated_fat": 0.0, "trans_fat": 0.0,
            "fiber": 4.5, "cholesterol": 0.0, "sodium": 75.0,
            "ingredients": "Fresh country sweet potatoes, sea salt.",
            "allergens": "None", "serving_size": "1 plate (150g)", "cooking_method": "Steamed"
        }
    },
    {
        "num": 36,
        "name": "Cucumber and Carrot with Yogurt Dip",
        "malayalam_name": "വെള്ളരി-കാരറ്റ് സാലഡും തൈര് ഡിപ്പും",
        "description": "Crisp, chilled cucumber and carrot batons served with a refreshing, probiotic-rich spiced hung curd and mint dip.",
        "malayalam_description": "പുതിയ കാരറ്റും വെള്ളരിയും പുതിനയിട്ട തൈര് ഡിപ്പും.",
        "session": "Evening Snacks",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": False,
        "contains_egg": False,
        "price": 50.00,
        "image": "/media/food_photos/new/snacks/cucumber_carrot_sticks_dip.jpg",
        "nutrition": {
            "calories": 95.0, "protein": 4.2, "carbohydrates": 12.0, "total_sugars": 4.5,
            "added_sugars": 0.0, "total_fat": 2.8, "saturated_fat": 1.6, "trans_fat": 0.0,
            "fiber": 3.2, "cholesterol": 6.0, "sodium": 95.0,
            "ingredients": "English cucumber, juicy carrots, hung curd (Greek style), fresh mint, roasted cumin, black salt.",
            "allergens": "Dairy", "serving_size": "1 plate batons + 50ml dip", "cooking_method": "Fresh raw chilled"
        }
    },
    {
        "num": 37,
        "name": "Dry-Roasted Peanuts",
        "malayalam_name": "വറുത്ത കപ്പലണ്ടി",
        "description": "Crunchy oven-roasted whole peanuts seasoned lightly with salt and roasted cumin, packed with healthy fats and protein.",
        "malayalam_description": "രുചികരമായി വറുത്തെടുത്ത നാടൻ നിലക്കടല.",
        "session": "Evening Snacks",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 35.00,
        "image": "/media/food_photos/new/snacks/boiled_peanut_sundal.jpg",
        "nutrition": {
            "calories": 165.0, "protein": 7.4, "carbohydrates": 6.5, "total_sugars": 1.2,
            "added_sugars": 0.0, "total_fat": 13.5, "saturated_fat": 2.0, "trans_fat": 0.0,
            "fiber": 2.8, "cholesterol": 0.0, "sodium": 80.0,
            "ingredients": "Whole shelled peanuts, roasted cumin powder, pink salt.",
            "allergens": "Peanuts", "serving_size": "1 small bowl (30g)", "cooking_method": "Dry-roasted"
        }
    },
    {
        "num": 38,
        "name": "Steamed Nendran Banana",
        "malayalam_name": "പുഴുങ്ങിയ നേന്ത്രപ്പഴം",
        "description": "Naturally sweet ripe Kerala Nendran banana gently steamed in its skin, preserving dietary fibers and essential potassium.",
        "malayalam_description": "ആവിയിൽ പുഴുങ്ങിയ പഴുത്ത നാടൻ നേന്ത്രപ്പഴം.",
        "session": "Evening Snacks",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 35.00,
        "image": "/media/food_photos/new/snacks/steamed_ethakka_nendran_banana.jpg",
        "nutrition": {
            "calories": 145.0, "protein": 1.6, "carbohydrates": 35.0, "total_sugars": 14.0,
            "added_sugars": 0.0, "total_fat": 0.4, "saturated_fat": 0.1, "trans_fat": 0.0,
            "fiber": 3.8, "cholesterol": 0.0, "sodium": 15.0,
            "ingredients": "Ripe Kerala Nendran banana.",
            "allergens": "None", "serving_size": "1 whole banana sliced (150g)", "cooking_method": "Steamed"
        }
    },
    {
        "num": 39,
        "name": "Boiled Egg",
        "malayalam_name": "പുഴുങ്ങിയ കോഴിമുട്ട",
        "description": "Perfect hard-boiled farm-fresh eggs served with a dusting of freshly ground Malabar black pepper and pink salt.",
        "malayalam_description": "കുരുമുളകുപൊടിയും ഉപ്പും വിതറിയ പുഴുങ്ങിയ കോഴിമുട്ട.",
        "session": "Evening Snacks",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": True,
        "price": 30.00,
        "image": "/media/food_photos/boiled_egg.jpg",
        "nutrition": {
            "calories": 140.0, "protein": 12.6, "carbohydrates": 1.1, "total_sugars": 0.6,
            "added_sugars": 0.0, "total_fat": 9.5, "saturated_fat": 3.1, "trans_fat": 0.0,
            "fiber": 0.0, "cholesterol": 370.0, "sodium": 140.0,
            "ingredients": "Farm-fresh eggs, Malabar black pepper, pink rock salt.",
            "allergens": "Eggs", "serving_size": "2 whole boiled eggs", "cooking_method": "Hard-boiled"
        }
    },
    {
        "num": 40,
        "name": "Steamed Fish Cakes",
        "malayalam_name": "ആവിയിൽ വേവിച്ച ഫിഷ് കേക്ക്",
        "description": "Minced white fish patties blended with shallots, ginger, green chilies, and herbs, gently steamed for a lean, high-protein snack.",
        "malayalam_description": "മീനും പച്ചക്കറികളും അരച്ച് ആവിയിൽ പുഴുങ്ങിയ ഫിഷ് കേക്ക്.",
        "session": "Evening Snacks",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 80.00,
        "image": "/media/food_photos/streamed fish.png",
        "nutrition": {
            "calories": 155.0, "protein": 18.5, "carbohydrates": 4.5, "total_sugars": 0.8,
            "added_sugars": 0.0, "total_fat": 6.8, "saturated_fat": 1.2, "trans_fat": 0.0,
            "fiber": 1.2, "cholesterol": 45.0, "sodium": 210.0,
            "ingredients": "Minced white fish fillet, shallots, ginger, green chilies, curry leaves, crushed pepper, pinch of salt.",
            "allergens": "Fish", "serving_size": "3 steamed patties (120g)", "cooking_method": "Steamed"
        }
    },

    # =========================================================================
    # DINNER — Items 41–50 (10 Items)
    # =========================================================================
    {
        "num": 41,
        "name": "Whole-Wheat Chapati with Vegetable Kurma",
        "malayalam_name": "ഗോതമ്പ് ചപ്പാത്തിയും വെജിറ്റബിൾ കുറുമയും",
        "description": "Tender whole-wheat flatbreads served with a creamy, aromatic vegetable kurma prepared with coconut milk and mild Kerala spices.",
        "malayalam_description": "ചപ്പാത്തിയും പച്ചക്കറികൾ ചേർത്ത നാടൻ വെജ് കുറുമയും.",
        "session": "Dinner",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 80.00,
        "image": "/media/food_photos/new/dinner/multi_millet_chapati_veg_kurma.jpg",
        "nutrition": {
            "calories": 270.0, "protein": 7.2, "carbohydrates": 44.0, "total_sugars": 2.8,
            "added_sugars": 0.0, "total_fat": 6.5, "saturated_fat": 3.5, "trans_fat": 0.0,
            "fiber": 6.5, "cholesterol": 0.0, "sodium": 210.0,
            "ingredients": "Whole-wheat flour, potatoes, carrots, green peas, light coconut milk, fennel, cinnamon, cloves.",
            "allergens": "Wheat (Gluten)", "serving_size": "2 chapatis + 150ml kurma", "cooking_method": "Griddled & simmered"
        }
    },
    {
        "num": 42,
        "name": "Appam with Light Vegetable Stew",
        "malayalam_name": "അപ്പവും ലൈറ്റ് വെജിറ്റബിൾ സ്റ്റൂവും",
        "description": "Soft, feather-light rice hoppers with a spongy center, paired with an easily digestible evening coconut milk vegetable stew.",
        "malayalam_description": "അത്താഴത്തിന് അനുയോജ്യമായ മൃദുവായ അപ്പവും ലൈറ്റ് സ്റ്റൂവും.",
        "session": "Dinner",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 80.00,
        "image": "/media/food_photos/dinner_appam_with_vegetable_stew_1243.jpg",
        "nutrition": {
            "calories": 240.0, "protein": 4.8, "carbohydrates": 43.0, "total_sugars": 2.4,
            "added_sugars": 0.0, "total_fat": 5.2, "saturated_fat": 3.8, "trans_fat": 0.0,
            "fiber": 4.0, "cholesterol": 0.0, "sodium": 175.0,
            "ingredients": "Fermented rice, thin coconut milk, carrots, potatoes, green peas, whole ginger, green chilies.",
            "allergens": "None", "serving_size": "2 appams + 150ml stew", "cooking_method": "Appachatti griddled & stewed"
        }
    },
    {
        "num": 43,
        "name": "Whole-Wheat Pathiri with Green Gram Curry",
        "malayalam_name": "ഗോതമ്പ് പത്തിരിയും ചെറുപയർ കറിയും",
        "description": "Delicate whole-wheat rolled pathiri served with a savory, protein-rich stewed green gram gravy.",
        "malayalam_description": "കനംകുറഞ്ഞ ഗോതമ്പ് പത്തിരിയും ചെറുപയർ കറിയും.",
        "session": "Dinner",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 75.00,
        "image": "/media/food_photos/Soft Malabar Pathiri & Veg Kurma.png",
        "nutrition": {
            "calories": 250.0, "protein": 8.8, "carbohydrates": 44.0, "total_sugars": 1.6,
            "added_sugars": 0.0, "total_fat": 3.8, "saturated_fat": 1.6, "trans_fat": 0.0,
            "fiber": 7.4, "cholesterol": 0.0, "sodium": 190.0,
            "ingredients": "Fine whole-wheat flour, whole green gram, shallots, garlic, turmeric, mustard, curry leaves.",
            "allergens": "Wheat (Gluten)", "serving_size": "3 pathiris + 150ml curry", "cooking_method": "Dry tawa griddled"
        }
    },
    {
        "num": 44,
        "name": "Vegetable Broken Wheat Khichdi",
        "malayalam_name": "നുറുക്ക് ഗോതമ്പ് വെജിറ്റബിൾ ഖിച്ഡി",
        "description": "Nutritious one-pot dinner of cracked wheat, yellow moong dal, carrots, and green beans, lightly tempered with cumin and ghee.",
        "malayalam_description": "ഗോതമ്പ് നുറുക്കും പരിപ്പും പച്ചക്കറികളും ചേർത്ത ലളിതമായ ഖിച്ഡി.",
        "session": "Dinner",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": False,
        "contains_egg": False,
        "price": 85.00,
        "image": "/media/food_photos/new/dinner/broken_wheat_vegetable_khichdi.jpg",
        "nutrition": {
            "calories": 240.0, "protein": 8.5, "carbohydrates": 42.0, "total_sugars": 1.8,
            "added_sugars": 0.0, "total_fat": 4.0, "saturated_fat": 1.8, "trans_fat": 0.0,
            "fiber": 7.8, "cholesterol": 4.0, "sodium": 185.0,
            "ingredients": "Broken wheat, split yellow moong dal, carrots, french beans, cumin seeds, pure cow ghee, ginger.",
            "allergens": "Wheat, Dairy (Ghee)", "serving_size": "1 large bowl (300g)", "cooking_method": "One-pot pressure cooked"
        }
    },
    {
        "num": 45,
        "name": "Kerala-Style Vegetable Soup",
        "malayalam_name": "നാടൻ വെജിറ്റബിൾ സൂപ്പ്",
        "description": "Clear, revitalizing vegetable broth infused with crushed shallots, ginger, garlic, black peppercorns, and fresh coriander.",
        "malayalam_description": "കുരുമുളകും ഇഞ്ചിയും ചേർത്ത നാടൻ പച്ചക്കറി ക്ലിയർ സൂപ്പ്.",
        "session": "Dinner",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 60.00,
        "image": "/media/food_photos/kerala_vegetable_soup.jpg",
        "nutrition": {
            "calories": 85.0, "protein": 2.5, "carbohydrates": 14.0, "total_sugars": 2.5,
            "added_sugars": 0.0, "total_fat": 1.2, "saturated_fat": 0.2, "trans_fat": 0.0,
            "fiber": 3.8, "cholesterol": 0.0, "sodium": 160.0,
            "ingredients": "Carrots, beans, shallots, ginger, garlic, crushed black pepper, fresh coriander, vegetable stock.",
            "allergens": "None", "serving_size": "1 bowl (250ml)", "cooking_method": "Simmered broth"
        }
    },
    {
        "num": 46,
        "name": "Grilled Fish with Steamed Vegetables",
        "malayalam_name": "ഗ്രിൽഡ് ഫിഷും പച്ചക്കറികളും",
        "description": "Pan-grilled fish fillet lightly spiced with turmeric and pepper, served alongside steamed broccoli, carrots, and beans.",
        "malayalam_description": "കുരുമുളകും മഞ്ഞളും പുരട്ടി ഗ്രിൽ ചെയ്ത മീനും ആവിയിൽ വേവിച്ച പച്ചക്കറികളും.",
        "session": "Dinner",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 150.00,
        "image": "/media/food_photos/new/dinner/grilled_seer_fish_steamed_veg.jpg",
        "nutrition": {
            "calories": 260.0, "protein": 28.0, "carbohydrates": 10.5, "total_sugars": 2.0,
            "added_sugars": 0.0, "total_fat": 8.5, "saturated_fat": 1.6, "trans_fat": 0.0,
            "fiber": 4.5, "cholesterol": 60.0, "sodium": 220.0,
            "ingredients": "Fresh seer fish/ayakoora fillet, broccoli, carrots, beans, lemon juice, turmeric, black pepper.",
            "allergens": "Fish", "serving_size": "1 grilled fillet + 120g steamed vegetables", "cooking_method": "Pan-grilled & steamed"
        }
    },
    {
        "num": 47,
        "name": "Light Chicken Stew with Whole-Wheat Chapati",
        "malayalam_name": "ചിക്കൻ സ്റ്റൂവും ഗോതമ്പ് ചപ്പാത്തിയും",
        "description": "Whole-wheat chapatis paired with tender chicken pieces gently stewed with carrots, potatoes, and mild whole spices.",
        "malayalam_description": "നേർത്ത തേങ്ങാപ്പാലിൽ തയ്യാറാക്കിയ ചിക്കൻ സ്റ്റൂവും ചപ്പാത്തിയും.",
        "session": "Dinner",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 120.00,
        "image": "/media/food_photos/new/dinner/chicken_breast_stew_with_chapati.jpg",
        "nutrition": {
            "calories": 340.0, "protein": 22.0, "carbohydrates": 38.0, "total_sugars": 2.2,
            "added_sugars": 0.0, "total_fat": 9.2, "saturated_fat": 3.8, "trans_fat": 0.0,
            "fiber": 5.2, "cholesterol": 50.0, "sodium": 270.0,
            "ingredients": "Whole-wheat flour, chicken breast cubes, light coconut milk, potatoes, carrots, cinnamon, black pepper.",
            "allergens": "Wheat (Gluten)", "serving_size": "2 chapatis + 180ml stew", "cooking_method": "Griddled & stewed"
        }
    },
    {
        "num": 48,
        "name": "Egg Curry with Whole-Wheat Chapati",
        "malayalam_name": "മുട്ടക്കറിയും ഗോതമ്പ് ചപ്പാത്തിയും",
        "description": "Nutritious whole-wheat flatbreads served with boiled eggs in a mildly spiced tomato, onion, and coconut curry.",
        "malayalam_description": "നാടൻ മുട്ടക്കറിയും മൃദുവായ ഗോതമ്പ് ചപ്പാത്തിയും.",
        "session": "Dinner",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": True,
        "price": 95.00,
        "image": "/media/food_photos/egg_curry_whole_wheat_chapati.jpg",
        "nutrition": {
            "calories": 310.0, "protein": 14.0, "carbohydrates": 36.0, "total_sugars": 2.6,
            "added_sugars": 0.0, "total_fat": 10.5, "saturated_fat": 2.9, "trans_fat": 0.0,
            "fiber": 5.2, "cholesterol": 185.0, "sodium": 280.0,
            "ingredients": "Whole-wheat flour, eggs, onions, tomatoes, ginger, fennel seeds, light coconut milk, curry leaves.",
            "allergens": "Eggs, Wheat (Gluten)", "serving_size": "2 chapatis + 2 eggs in curry", "cooking_method": "Griddled & curried"
        }
    },
    {
        "num": 49,
        "name": "Grilled Chicken with Vegetables",
        "malayalam_name": "ഗ്രിൽഡ് ചിക്കനും പച്ചക്കറികളും",
        "description": "Herb-marinated lean chicken breast grilled to perfection and served with a colorful medley of sautéed garden vegetables.",
        "malayalam_description": "ആരോഗ്യപ്രദമായ ഗ്രിൽഡ് ചിക്കൻ ബ്രെസ്റ്റും പച്ചക്കറികളും.",
        "session": "Dinner",
        "category": "Non-Vegetarian",
        "is_veg": False,
        "is_vegan": False,
        "contains_egg": False,
        "price": 145.00,
        "image": "/media/food_photos/grilled_chicken_with_vegetables.jpg",
        "nutrition": {
            "calories": 285.0, "protein": 31.0, "carbohydrates": 9.0, "total_sugars": 2.2,
            "added_sugars": 0.0, "total_fat": 8.0, "saturated_fat": 1.8, "trans_fat": 0.0,
            "fiber": 3.8, "cholesterol": 70.0, "sodium": 240.0,
            "ingredients": "Skinless chicken breast fillet, zucchini, bell peppers, carrots, broccoli, olive oil, rosemary, black pepper.",
            "allergens": "None", "serving_size": "1 grilled breast (160g) + 120g vegetables", "cooking_method": "Grill-charred"
        }
    },
    {
        "num": 50,
        "name": "Tofu and Vegetable Stir-Fry",
        "malayalam_name": "ടോഫു പച്ചക്കറി സ്റ്റിർ-ഫ്രൈ",
        "description": "Crisp pan-seared tofu cubes tossed with bell peppers, beans, carrots, and a light soy-ginger Kerala spiced glaze.",
        "malayalam_description": "പ്രോട്ടീൻ സമ്പന്നമായ ടോഫുവും പച്ചക്കറികളും ചേർത്ത സ്റ്റിർ-ഫ്രൈ.",
        "session": "Dinner",
        "category": "Vegetarian",
        "is_veg": True,
        "is_vegan": True,
        "contains_egg": False,
        "price": 110.00,
        "image": "/media/food_photos/tofu_vegetable_stir_fry.jpg",
        "nutrition": {
            "calories": 210.0, "protein": 14.5, "carbohydrates": 14.0, "total_sugars": 2.8,
            "added_sugars": 0.0, "total_fat": 9.5, "saturated_fat": 1.4, "trans_fat": 0.0,
            "fiber": 5.2, "cholesterol": 0.0, "sodium": 260.0,
            "ingredients": "Organic firm tofu, bell peppers (capsicum), green beans, broccoli, ginger, garlic, sesame oil, curry leaves.",
            "allergens": "Soy", "serving_size": "1 large bowl (250g)", "cooking_method": "Wok stir-fried"
        }
    }
]

class Command(BaseCommand):
    help = "Seeds the exact 50-food health catalogue in Veetile-Ruchi with complete nutrition and image matching."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Beginning seed of exact 50-food health catalogue..."))

        # 1. Fetch or create Categories
        cat_veg, _ = Category.objects.get_or_create(name="Vegetarian", defaults={"description": "Vegetarian Kerala dishes"})
        cat_nonveg, _ = Category.objects.get_or_create(name="Non-Vegetarian", defaults={"description": "Non-Vegetarian Kerala dishes"})
        Category.objects.get_or_create(name="Desserts", defaults={"description": "Traditional Kerala sweets"})

        # 2. Fetch or create MealSessions
        session_map = {}
        for s_name, (st, et) in {
            "Morning Breakfast": ("06:00:00", "12:00:00"),
            "Lunch": ("12:00:00", "16:00:00"),
            "Evening Snacks": ("16:00:00", "19:00:00"),
            "Dinner": ("19:00:00", "23:59:59")
        }.items():
            sess_obj, _ = MealSession.objects.get_or_create(
                name=s_name,
                defaults={"start_time": st, "end_time": et}
            )
            session_map[s_name] = sess_obj

        # 3. Chef user assignment
        chef_user = User.objects.filter(role="chef").first()
        if not chef_user:
            chef_user = User.objects.filter(is_staff=True).first()

        with transaction.atomic():
            # Inventory existing foods
            existing_foods = list(FoodItem.objects.all())
            self.stdout.write(f"Existing foods in database: {len(existing_foods)}")

            reused_count = 0
            updated_count = 0
            created_count = 0

            # Map target foods by name lowercase for exact matching
            target_by_name = {item["name"].lower(): item for item in EXACT_50_FOOD_CATALOGUE}
            processed_target_names = set()

            # Pass 1: Update existing foods that match target names
            for food in existing_foods:
                norm_name = food.name.strip().lower()
                # Check for direct or close match
                matched_target = target_by_name.get(norm_name)
                if not matched_target:
                    # Fuzzy / alternate naming match
                    if "puttu" in norm_name and "kadala" in norm_name:
                        matched_target = target_by_name.get("puttu with kadala curry")
                    elif "idli" in norm_name and "sambar" in norm_name:
                        matched_target = target_by_name.get("idli with sambar")
                    elif "appam" in norm_name and "stew" in norm_name and "veg" in norm_name:
                        matched_target = target_by_name.get("appam with vegetable stew")
                    elif "dosa" in norm_name and "sambar" in norm_name and "ragi" not in norm_name:
                        matched_target = target_by_name.get("plain dosa with sambar")
                    elif "ela ada" in norm_name:
                        matched_target = target_by_name.get("ela ada")
                    elif "kozhukatta" in norm_name:
                        matched_target = target_by_name.get("steamed kozhukatta")

                if matched_target and matched_target["name"].lower() not in processed_target_names:
                    # Reuse existing record
                    target = matched_target
                    food.name = target["name"]
                    food.malayalam_name = target["malayalam_name"]
                    food.description = target["description"]
                    food.malayalam_description = target["malayalam_description"]
                    food.meal_session = session_map[target["session"]]
                    food.category = cat_veg if target["is_veg"] else cat_nonveg
                    food.is_vegetarian = target["is_veg"]
                    food.is_vegan = target["is_vegan"]
                    food.contains_egg = target["contains_egg"]
                    food.price = target["price"]
                    food.stock_quantity = 20
                    food.is_available = True
                    food.image = target["image"]
                    if chef_user and not food.chef:
                        food.chef = chef_user
                    food.save()

                    # Save nutrition
                    nutr_data = target["nutrition"]
                    NutritionInfo.objects.update_or_create(
                        food_item=food,
                        defaults=nutr_data
                    )
                    processed_target_names.add(target["name"].lower())
                    reused_count += 1

            # Pass 2: Reuse remaining unallocated existing food records to satisfy remaining targets
            unallocated_existing = [f for f in existing_foods if f.name.lower() not in processed_target_names]
            for target in EXACT_50_FOOD_CATALOGUE:
                if target["name"].lower() in processed_target_names:
                    continue

                if unallocated_existing:
                    # Safe reuse of an existing record
                    food = unallocated_existing.pop(0)
                    food.name = target["name"]
                    food.malayalam_name = target["malayalam_name"]
                    food.description = target["description"]
                    food.malayalam_description = target["malayalam_description"]
                    food.meal_session = session_map[target["session"]]
                    food.category = cat_veg if target["is_veg"] else cat_nonveg
                    food.is_vegetarian = target["is_veg"]
                    food.is_vegan = target["is_vegan"]
                    food.contains_egg = target["contains_egg"]
                    food.price = target["price"]
                    food.stock_quantity = 20
                    food.is_available = True
                    food.image = target["image"]
                    if chef_user and not food.chef:
                        food.chef = chef_user
                    food.save()

                    nutr_data = target["nutrition"]
                    NutritionInfo.objects.update_or_create(
                        food_item=food,
                        defaults=nutr_data
                    )
                    processed_target_names.add(target["name"].lower())
                    updated_count += 1
                else:
                    # Create new food record
                    food = FoodItem.objects.create(
                        name=target["name"],
                        malayalam_name=target["malayalam_name"],
                        description=target["description"],
                        malayalam_description=target["malayalam_description"],
                        meal_session=session_map[target["session"]],
                        category=cat_veg if target["is_veg"] else cat_nonveg,
                        is_vegetarian=target["is_veg"],
                        is_vegan=target["is_vegan"],
                        contains_egg=target["contains_egg"],
                        price=target["price"],
                        stock_quantity=20,
                        is_available=True,
                        image=target["image"],
                        chef=chef_user
                    )
                    nutr_data = target["nutrition"]
                    NutritionInfo.objects.create(
                        food_item=food,
                        **nutr_data
                    )
                    processed_target_names.add(target["name"].lower())
                    created_count += 1

            # Pass 3: If any extra unallocated existing records remain (beyond the 50), verify and remove safely
            if unallocated_existing:
                for leftover in unallocated_existing:
                    leftover.delete()

        # Verification & Audit
        final_foods = FoodItem.objects.all().select_related('meal_session', 'category', 'nutrition')
        total_final = final_foods.count()

        sess_counts = {}
        for f in final_foods:
            s_name = f.meal_session.name if f.meal_session else 'Unassigned'
            sess_counts[s_name] = sess_counts.get(s_name, 0) + 1

        self.stdout.write(self.style.SUCCESS(f"\n========================================================"))
        self.stdout.write(self.style.SUCCESS(f"50-FOOD HEALTH CATALOGUE IMPORT COMPLETED SUCCESSFULLY!"))
        self.stdout.write(self.style.SUCCESS(f"========================================================"))
        self.stdout.write(f"Total Foods in Database: {total_final} (Target: 50)")
        self.stdout.write(f"Existing records reused: {reused_count}")
        self.stdout.write(f"Existing records updated: {updated_count}")
        self.stdout.write(f"New records created: {created_count}")
        self.stdout.write(f"Distribution by Session:")
        for s, c in sess_counts.items():
            self.stdout.write(f"  * {s}: {c}")

        # Check unique images
        images = [f.image for f in final_foods]
        unique_images = set(images)
        self.stdout.write(f"Unique images assigned: {len(unique_images)} / {total_final}")
