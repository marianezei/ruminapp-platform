from django.urls import path

from . import views

urlpatterns = [
    path("", views.painel, name="painel"),
    path("animais/", views.animal_lista, name="animal_lista"),
    path("animais/novo/", views.animal_form, name="animal_novo"),
    path("animais/<int:pk>/", views.animal_detalhe, name="animal_detalhe"),
    path("animais/<int:pk>/editar/", views.animal_form, name="animal_editar"),
    path("eventos/novo/", views.evento_novo, name="evento_novo"),
    path("pesagens/nova/", views.pesagem_nova, name="pesagem_nova"),
    path("pesagens/<int:pk>/excluir/", views.pesagem_excluir, name="pesagem_excluir"),
    path("eventos/<int:pk>/excluir/", views.evento_excluir, name="evento_excluir"),
    path("parametros/", views.configuracao, name="configuracao"),
    path("aparencia/", views.aparencia, name="aparencia"),
    path("aparencia/previa.css", views.aparencia_previa, name="aparencia_previa"),
]
