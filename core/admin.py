# myproject/myapp/admin.py

from django.contrib import admin
from .models import Category, Page # Importiere deine Models

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
