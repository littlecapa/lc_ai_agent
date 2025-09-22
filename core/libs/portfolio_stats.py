from ..models.stock_models import Stock, Holdings, Alarm, Recommendation
from django.db.models import F, Sum

def get_stats():
    total_stocks = Stock.objects.count()
    total_alarms = Alarm.objects.filter(is_active=True).count()
    total_recom = Recommendation.objects.count()
    holdings = Holdings.objects.aggregate(
        total=Sum(F('quantity') * F('average_purchase_price'))
    )['total']
    return {
        'total_stocks': total_stocks,
        'total_alarms': total_alarms or 0,
        'total_recommendations': total_recom,
        'total_holdings_value': holdings or 0
    }