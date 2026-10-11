"""
Deixa o banco pronto para uso: cria os usuários definidos no ambiente e, se o banco
estiver vazio, gera um rebanho sintético. Pode rodar várias vezes sem efeito colateral.
"""
import os

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand

from rebanho.models import Animal


class Command(BaseCommand):
    help = "Cria os usuários iniciais e popula o banco com dados sintéticos se estiver vazio"

    def handle(self, *args, **opts):
        self._usuario("RUMINAPP_ADMIN_USUARIO", "RUMINAPP_ADMIN_SENHA", admin=True)
        self._usuario("RUMINAPP_LOADGEN_USUARIO", "RUMINAPP_LOADGEN_SENHA", admin=False)
        if Animal.objects.exists():
            self.stdout.write("Banco já tem animais; dados sintéticos não foram gerados.")
        else:
            call_command("popular_exemplo", stdout=self.stdout)

    def _usuario(self, var_usuario, var_senha, admin):
        nome, senha = os.environ.get(var_usuario), os.environ.get(var_senha)
        if not nome or not senha:
            return
        usuario, criado = User.objects.get_or_create(username=nome)
        usuario.is_staff = usuario.is_superuser = admin
        usuario.set_password(senha)
        usuario.save()
        self.stdout.write(f"Usuário {nome} {'criado' if criado else 'atualizado'}.")
