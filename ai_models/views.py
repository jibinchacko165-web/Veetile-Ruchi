from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Sum, Count
from food.models import FoodItem, ReviewSentiment
from orders.models import Order, Payment
from accounts.models import User
from accounts.decorators import role_required
from delivery.models import DeliveryAssignment
from .models import FoodDemandForecast, FoodWastePrediction, StockPrediction, CustomerBehavior

@login_required
@role_required('admin', 'staff')
def ai_analytics_dashboard(request):
    """Business Intelligence reports displaying systems-wide AI prediction outputs."""
        
    # 1. Sentiment analysis report
    sentiment_stats = ReviewSentiment.objects.values('sentiment').annotate(count=Count('id'), avg_rating=Avg('rating'))
    
    # 2. Demand forecasts report
    demand_forecasts = FoodDemandForecast.objects.all().order_by('-forecast_date', '-predicted_quantity')[:10]
    
    # 3. Food waste report
    waste_predictions = FoodWastePrediction.objects.all().order_by('-prediction_date', '-predicted_waste_quantity')[:10]
    
    # 4. Stock predictions report
    stock_warnings = StockPrediction.objects.filter(predicted_days_until_out_of_stock__lt=3.0).order_by('predicted_days_until_out_of_stock')
    
    # 5. Customer Behavior segment counts
    behavior_segments = CustomerBehavior.objects.values('behavior_segment').annotate(count=Count('id'), avg_orders=Avg('total_orders_count'), avg_spend=Avg('average_order_value'))
    
    # 6. Delivery predictions vs actual accuracy comparison
    completed_deliveries = DeliveryAssignment.objects.filter(status='delivered', actual_delivery_time__isnull=False)
    avg_predicted_time = completed_deliveries.aggregate(Avg('predicted_delivery_time'))['predicted_delivery_time__avg'] or 0.0
    avg_actual_time = completed_deliveries.aggregate(Avg('actual_delivery_time'))['actual_delivery_time__avg'] or 0.0
    
    context = {
        'sentiment_stats': sentiment_stats,
        'demand_forecasts': demand_forecasts,
        'waste_predictions': waste_predictions,
        'stock_warnings': stock_warnings,
        'behavior_segments': behavior_segments,
        'avg_predicted_time': round(avg_predicted_time, 1),
        'avg_actual_time': round(avg_actual_time, 1),
        'completed_deliveries_count': completed_deliveries.count(),
    }
    return render(request, 'ai_models/analytics_dashboard.html', context)
