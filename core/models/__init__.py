from .stock_models import Stock, Holdings, Alarm, Recommendation, DecicionLog, SavingPlan
from .gmail_config_models import gmailShareConfig
from .page_models import Category, Page 

# Alle Models für Django verfügbar machen
__all__ = ['Stock', 'Holdings', 'Alarm', 'Recommendation', 'gmailShareConfig', 'Category', 'Page', 'DecicionLog', 'SavingPlan']