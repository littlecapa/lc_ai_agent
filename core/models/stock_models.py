from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.utils import timezone

class Stock(models.Model):
    """
    Grundsätzliche Informationen zu einer Aktie
    """
    # Als PK empfehle ich ISIN, da sie international eindeutig ist
    isin = models.CharField(
        max_length=12, 
        primary_key=True,
        verbose_name="ISIN",
        help_text="Internationale Wertpapierkennnummer (12 Zeichen)",
    )
    wkn = models.CharField(
        max_length=6, 
        unique=True, 
        null=True, 
        blank=True,
        help_text="Wertpapierkennnummer (6 Zeichen, hauptsächlich für deutsche Werte)",
    )
    symbol = models.CharField(
        max_length=10,
        help_text="Börsenkürzel (z.B. AAPL, SAP)",
        null=True, blank=True
    )
    name = models.CharField(
        max_length=200,
        help_text="Vollständiger Name der Aktie/Unternehmens"
    )
    currency = models.CharField(
        max_length=3,
        default='EUR',
        help_text="Währung als ISO-Code (EUR, USD, etc.)"
    )
    exchange = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Hauptbörse (XETRA, NYSE, NASDAQ, etc.)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Aktie"
        verbose_name_plural = "Aktien"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class Holdings(models.Model):
    """
    Bestand an Aktien pro Benutzer
    """
    CATEGORY_CHOICES = [
        (1, 'Basis Investment'),
        (2, 'Dividende'),
        (3, 'D/EU'),
        (4, 'US Tech'),
        (5, 'World Tech'),
        (99, 'Sonstiges'),
    ]
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='holdings'
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.000001'))],
        help_text="Anzahl gehaltener Aktien (auch Bruchteile möglich)"
    )
    average_purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Durchschnittlicher Einkaufspreis"
    )
    category = models.IntegerField(
        choices=CATEGORY_CHOICES,
        default=CATEGORY_CHOICES[-1][0], # Standardmäßig 'Sonstiges' (99)
        null=True,
        blank=True,
        help_text="Vertrauensgrad der Empfehlung"
    )
    notes = models.TextField(
        help_text="Persönliche Notizen zu dieser Position",
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bestand"
        verbose_name_plural = "Bestände"
        unique_together = ['stock']
        ordering = ['-quantity']

    def __str__(self):
        return f"{self.stock.name}: {self.quantity} ({self.stock.symbol})"

    @property
    def total_investment(self):
        """Gesamtinvestition berechnen"""
        if self.average_purchase_price:
            return self.quantity * self.average_purchase_price
        return None


class Alarm(models.Model):
    """
    Schwellwerte für Aktien mit Benachrichtigungen
    """
    
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='alarms'
    )
    
    threshold_value_high = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Schwellwert (Preis)",
        null=True, blank=True
    )
    threshold_value_low = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Schwellwert (Preis)",
        null=True, blank=True
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Alarm ist aktiv"
    )

    notes = models.TextField(
        help_text="Persönliche Notizen zu diesem Alarm",
        null=True, blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Alarm"
        verbose_name_plural = "Alarme"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.stock.symbol} {self.threshold_value_high} {self.threshold_value_low}"


class Recommendation(models.Model):
    """
    Empfehlungen zu Aktien von verschiedenen Quellen
    """
    STRATEGY_CHOICES = [
        (1, 'Safety First'),
        (2, 'Dividende'),
        (3, 'AI'),
        (4, 'sonstige Tech'),
        (5, 'Defense'),
        (6, 'Turnaround Kandidat'),
        (7, 'Burggraben'),
        (99, 'Sonstiges'),
    ]
    ACTION_CHOICES = [
        ('buy', 'Kaufen'),
        ('sell', 'Verkaufen'),
        ('hold', 'Halten'),
        ('strong_buy', 'Stark Kaufen'),
        ('strong_sell', 'Stark Verkaufen'),
    ]

    CONFIDENCE_CHOICES = [
        (1, 'Sehr niedrig'),
        (2, 'Niedrig'),
        (3, 'Mittel'),
        (4, 'Hoch'),
        (5, 'Sehr hoch'),
    ]

    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='recommendations'
    )
    action = models.CharField(
        max_length=15,
        choices=ACTION_CHOICES,
        default='hold',
        help_text="Empfohlene Aktion"
    )
    source = models.CharField(
        max_length=100,
        help_text="Quelle der Empfehlung (Analyst, Bank, Website, etc.)"
    )
    target_price = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Kursziel"
    )
    confidence = models.IntegerField(
        choices=CONFIDENCE_CHOICES,
        default=CONFIDENCE_CHOICES[2][0], # Standardmäßig 'Mittel' (3)
        null=True,
        blank=True,
        help_text="Vertrauensgrad der Empfehlung"
    )
    strategy = models.IntegerField(
        choices=STRATEGY_CHOICES,
        default=STRATEGY_CHOICES[-1][0], # Standardmäßig 'Sonstiges' (99)
        null=True,
        blank=True,
        help_text="Vertrauensgrad der Empfehlung"
    )
    reasoning = models.TextField(
        blank=True,
        help_text="Begründung für die Empfehlung"
    )
    publication_date = models.DateField(
        help_text="Datum der Veröffentlichung",
        null=True, blank=True
    )
    
    url = models.URLField(
        help_text="Link zur ursprünglichen Empfehlung",
        null=True, blank=True,
    )
    is_valid = models.BooleanField(
        default=True,
        help_text="Empfehlung ist noch gültig"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Empfehlung"
        verbose_name_plural = "Empfehlungen"
        ordering = ['-publication_date']

    def __str__(self):
        return f"{self.stock.symbol}: {self.get_action_display()} von {self.source}"

    @property
    def is_expired(self):
        """Prüft, ob die Empfehlung abgelaufen ist"""
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False