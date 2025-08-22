# myproject/myapp/models.py

from django.db import models

class Category(models.Model):
    """
    Repräsentiert eine Kategorie für Lesezeichen.
    Enthält eine Priorität für die Sortierung.
    """
    name = models.CharField(max_length=100, unique=True)
    priority = models.IntegerField(default=0, help_text="Priorität für die Sortierung der Kategorien (niedriger = zuerst)")

    class Meta:
        verbose_name_plural = "Categories" # Korrekter Plural für das Admin-Interface
        ordering = ['priority', 'name'] # Standard-Sortierung nach Priorität und dann Name

    def __str__(self):
        return self.name

class Page(models.Model):
    """
    Repräsentiert eine einzelne Lesezeichen-Seite innerhalb einer Kategorie.
    """
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='pages')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    url = models.URLField()
    icon = models.URLField(blank=True, null=True)

    class Meta:
        ordering = ['title'] # Standard-Sortierung nach Titel

    def __str__(self):
        return self.title

