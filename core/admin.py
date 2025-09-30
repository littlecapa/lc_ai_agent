# myproject/myapp/admin.py

from django.contrib import admin

from .models import Stock, Holdings, Alarm, Recommendation, Category, Page, gmailShareConfig


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['isin', 'symbol', 'name', 'currency', 'exchange']
    list_filter = ['currency', 'exchange']
    search_fields = ['isin', 'wkn', 'symbol', 'name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Grunddaten', {
            'fields': ('isin', 'wkn', 'symbol', 'name')
        }),
        ('Börsen-Info', {
            'fields': ('currency', 'exchange')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Holdings)
class HoldingsAdmin(admin.ModelAdmin):
    list_display = ['stock_id', 'quantity', 'average_purchase_price', 'total_investment_display']
    list_filter = ['stock_id', 'category']
    search_fields = ['isin', 'stock__symbol', 'stock__name']
    readonly_fields = ['created_at', 'updated_at', 'total_investment_display']
    autocomplete_fields = ['stock']  # Für bessere UX bei vielen Aktien
    
    fieldsets = (
        ('Position', {
            'fields': ('stock', 'quantity', 'average_purchase_price', 'category')
        }),
        ('Notizen', {
            'fields': ('notes',)
        }),
        ('Berechnungen', {
            'fields': ('total_investment_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def stock_symbol(self, obj):
        return obj.stock.symbol
    
    
    stock_symbol.short_description = 'Symbol'
    stock_symbol.admin_order_field = 'stock__symbol'
    
    def stock_id(self, obj):
        return f"{obj.stock.name}({obj.stock.isin})" 
    stock_id.short_description = 'Symbol'
    stock_id.admin_order_field = 'stock__name'

    
    def total_investment_display(self, obj):
        total = obj.total_investment
        if total:
            return f"{total:.2f} {obj.stock.currency}"
        return "-"
    total_investment_display.short_description = 'Gesamtinvestition'


@admin.register(Alarm)
class AlarmAdmin(admin.ModelAdmin):
    list_display = ['stock_symbol', 'threshold_value_low', 'threshold_value_high', 'is_active']
    list_filter = ['stock__symbol', 'stock__name', 'is_active']
    search_fields = ['stock__symbol']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['stock']
    
    fieldsets = (
        ('Alarm-Einstellungen', {
            'fields': ('stock', 'threshold_value_low', 'threshold_value_high', 'is_active', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def stock_symbol(self, obj):
        return obj.stock.symbol
    stock_symbol.short_description = 'Symbol'
    stock_symbol.admin_order_field = 'stock__symbol'

    # Aktionen für mehrere Alarme gleichzeitig
    actions = ['activate_alarms', 'deactivate_alarms']

    def activate_alarms(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} Alarme aktiviert.')
    activate_alarms.short_description = "Ausgewählte Alarme aktivieren"

    def deactivate_alarms(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} Alarme deaktiviert.')
    deactivate_alarms.short_description = "Ausgewählte Alarme deaktivieren"



@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ['stock_id', 'action', 'source', 'target_price', 'confidence', 'publication_date', 'is_valid']
    list_filter = ['action', 'confidence', 'strategy']
    search_fields = ['stock__symbol', 'stock__name', 'source']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['stock']
    date_hierarchy = 'publication_date'
    
    fieldsets = (
        ('Empfehlung', {
            'fields': ('stock', 'action', 'target_price', 'confidence', 'strategy')
        }),
        ('Quelle', {
            'fields': ('source', 'publication_date')
        }),
        ('Details', {
            'fields': ('reasoning', 'url', 'is_valid')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def stock_id(self, obj):
        return f"{obj.stock.name}({obj.stock.isin})" 
    stock_id.short_description = 'Symbol'
    stock_id.admin_order_field = 'stock__name'

    def is_expired_display(self, obj):
        if obj.is_expired:
            return "Ja ⚠️"
        return "Nein ✅"
    is_expired_display.short_description = 'Abgelaufen'

    # Aktionen für Empfehlungen
    actions = ['mark_as_invalid', 'mark_as_valid']

    def mark_as_invalid(self, request, queryset):
        updated = queryset.update(is_valid=False)
        self.message_user(request, f'{updated} Empfehlungen als ungültig markiert.')
    mark_as_invalid.short_description = "Als ungültig markieren"

    def mark_as_valid(self, request, queryset):
        updated = queryset.update(is_valid=True)
        self.message_user(request, f'{updated} Empfehlungen als gültig markiert.')
    mark_as_valid.short_description = "Als gültig markieren"

# Registriere das Category Model
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'priority') # Zeigt diese Felder in der Listenansicht an
    search_fields = ('name',) # Erlaubt die Suche nach dem Namen
    list_editable = ('priority',) # Erlaubt die direkte Bearbeitung der Priorität in der Liste
    list_filter = ('priority',) # Filter nach Priorität

# Registriere das Page Model
@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('title', 'url', 'category', 'icon') # Zeigt diese Felder an
    search_fields = ('title', 'description', 'url') # Erlaubt die Suche
    list_filter = ('category',) # Filter nach Kategorie
    # Füge eine Inline-Bearbeitung für Pages innerhalb der Category-Ansicht hinzu
    # Dadurch kannst du Pages direkt beim Bearbeiten einer Kategorie hinzufügen/ändern
    # Inlines werden oft in der CategoryAdmin-Klasse verwendet, aber zur Vereinfachung hier separat gezeigt.
    # Für Inlines in CategoryAdmin, siehe den optionalen Abschnitt unten.

admin.site.register(gmailShareConfig)