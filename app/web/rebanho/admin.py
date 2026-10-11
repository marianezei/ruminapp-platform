from django.contrib import admin

from .models import Animal, ConfiguracaoReprodutiva, Evento, Lote, Pesagem, PreferenciasVisuais, Touro


class EventoInline(admin.TabularInline):
    model = Evento
    extra = 0
    fields = ("data", "tipo", "touro", "inseminador", "resultado", "observacoes")


class PesagemInline(admin.TabularInline):
    model = Pesagem
    extra = 0


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ("brinco", "cor_brinco", "nome", "raca", "lote", "data_nascimento", "ativo")
    list_filter = ("ativo", "raca", "lote", "cor_brinco")
    search_fields = ("brinco", "nome")
    inlines = [EventoInline, PesagemInline]


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("data", "animal", "tipo", "touro", "resultado")
    list_filter = ("tipo", "data")
    search_fields = ("animal__brinco", "animal__nome")
    date_hierarchy = "data"


admin.site.register(Lote)
admin.site.register(Touro)
admin.site.register(ConfiguracaoReprodutiva)
@admin.register(Pesagem)
class PesagemAdmin(admin.ModelAdmin):
    list_display = ("data", "animal", "peso")
    search_fields = ("animal__brinco", "animal__nome")
    date_hierarchy = "data"


admin.site.register(PreferenciasVisuais)
