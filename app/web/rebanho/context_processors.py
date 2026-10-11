from django.utils.safestring import mark_safe

from . import tema
from .models import PreferenciasVisuais


def tema_visual(request):
    """Injeta o CSS do tema do usuário logado em todas as páginas."""
    css = None
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        prefs = PreferenciasVisuais.objects.filter(usuario=user).first()
        if prefs:
            try:
                css = prefs.css()
            except ValueError:
                css = None
    # As cores são validadas (#RRGGBB), então é seguro marcar como HTML seguro.
    return {"tema_css": mark_safe(css or tema.css_padrao())}
