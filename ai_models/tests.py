from django.test import TestCase
from ai_models.ml_engine import (
    analyze_review_sentiment,
    calculate_distance,
    predict_delivery_time,
    classify_health_profile_risk,
    predict_health_suitability,
    optimize_delivery_route
)

class AIMLTests(TestCase):
    def test_sentiment_analysis(self):
        """Tests that Naive Bayes correctly classifies positive and negative comments."""
        sentiment_pos, conf_pos = analyze_review_sentiment("The food was absolutely delicious and hot!")
        sentiment_neg, conf_neg = analyze_review_sentiment("The food was cold, stale, and tasted terrible.")
        
        self.assertEqual(sentiment_pos, 'positive')
        self.assertEqual(sentiment_neg, 'negative')
        self.assertTrue(conf_pos > 0.3)
        self.assertTrue(conf_neg > 0.3)

    def test_distance_calculation(self):
        """Tests that Haversine formula distance calculation is accurate."""
        # Distance between Chef (9.462534, 76.72185) and a point ~1.1km away (9.472534, 76.72185)
        dist = calculate_distance(9.462534, 76.72185, 9.472534, 76.72185)
        self.assertAlmostEqual(dist, 1.11, places=1)

    def test_delivery_time_prediction(self):
        """Tests that Random Forest predicts a reasonable delivery duration."""
        eta = predict_delivery_time(9.462534, 76.72185, 9.472534, 76.72185) # ~1.1km
        self.assertTrue(5.0 <= eta <= 25.0)

    def test_health_profile_risk(self):
        """Tests that Decision Tree risk classification assigns correct risk tiers."""
        risk_low = classify_health_profile_risk(False, False, False)
        risk_high = classify_health_profile_risk(True, True, True)
        
        self.assertEqual(risk_low, 'Low')
        self.assertEqual(risk_high, 'High')

    def test_health_suitability(self):
        """Tests that health suitability flags are correctly assessed."""
        suit_safe = predict_health_suitability(1.0, 5.0, 50.0) # healthy salad values
        suit_bad = predict_health_suitability(15.0, 50.0, 400.0) # high sugar/chol/sodium
        
        self.assertTrue(suit_safe['diabetes'])
        self.assertTrue(suit_safe['cholesterol'])
        self.assertTrue(suit_safe['bp'])
        
        self.assertFalse(suit_bad['diabetes'])
        self.assertFalse(suit_bad['cholesterol'])
        self.assertFalse(suit_bad['bp'])

    def test_route_optimization(self):
        """Tests that route optimizer generates step-by-step coordinates."""
        steps, dist = optimize_delivery_route(10.015, 76.325, 10.025, 76.315)
        self.assertTrue(len(steps) >= 3)
        self.assertEqual(steps[0]['lat'], 10.015)
        self.assertEqual(steps[-1]['lat'], 10.025)
