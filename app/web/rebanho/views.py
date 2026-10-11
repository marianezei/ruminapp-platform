from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AnimalForm, EventoForm, PesagemForm
from . import colunas as cols, tema
from .models import Animal, ConfiguracaoReprodutiva, Evento, Lote, Pesagem, PreferenciasVisuais
from .reproducao import calcular_lote, gerar_listas, indicadores


def carregar_animais(queryset=None, hoje=None):
    """Carrega animais com eventos e já calcula o status de cada um."""
    hoje = hoje or date.today()
    config = ConfiguracaoReprodutiva.atual()
    qs = (queryset if queryset is not None else Animal.objects.all())
    qs = qs.select_related("lote").prefetch_related("eventos__touro", "pesagens")
    animais = list(qs)
    status = calcular_lote(animais, config=config, hoje=hoje)
    for a in animais:
        a._status_cache = status[a.pk]
    return animais, config


@login_required
def painel(request):
    hoje = date.today()
    animais, config = carregar_animais(Animal.objects.filter(ativo=True), hoje)
    listas = gerar_listas(animais, config, hoje)
    return render(request, "rebanho/painel.html", {
        "hoje": hoje,
        "listas_acao": [l for l in listas if l.chave not in ("aptas", "problemas")],
        "aptas": next(l for l in listas if l.chave == "aptas"),
        "problemas": next(l for l in listas if l.chave == "problemas"),
        "ind": indicadores(animais, hoje),
    })


@login_required
def animal_lista(request):
    qs = Animal.objects.all()
    if request.GET.get("baixados") != "1":
        qs = qs.filter(ativo=True)
    busca = request.GET.get("q", "").strip()
    if busca:
        qs = qs.filter(Q(brinco__icontains=busca) | Q(nome__icontains=busca))
    if request.GET.get("lote"):
        qs = qs.filter(lote_id=request.GET["lote"])
    cor = request.GET.get("cor")
    if cor == "padrao":
        qs = qs.filter(cor_brinco="")
    elif cor:
        qs = qs.filter(cor_brinco=cor)

    animais, _ = carregar_animais(qs)

    if request.GET.get("categoria"):
        animais = [a for a in animais if a.status.categoria == request.GET["categoria"]]
    if request.GET.get("situacao"):
        animais = [a for a in animais if a.status.situacao == request.GET["situacao"]]

    # Filtro por tempo no estado: "vacas prenhes há mais de 200 dias", por exemplo.
    def inteiro(nome):
        valor = request.GET.get(nome, "").strip()
        return int(valor) if valor.lstrip("-").isdigit() else None

    dias_min, dias_max = inteiro("dias_min"), inteiro("dias_max")
    if dias_min is not None:
        animais = [a for a in animais if (a.status.dias_situacao or 0) >= dias_min]
    if dias_max is not None:
        animais = [a for a in animais if (a.status.dias_situacao or 0) <= dias_max]

    animais, chave, sentido = cols.ordenar(animais, request.GET.get("ordem"), request.GET.get("dir"))

    # Links de ordenação preservam os filtros que já estão na tela.
    parametros = request.GET.copy()
    parametros.pop("ordem", None)
    parametros.pop("dir", None)
    parametros.pop("page", None)

    return render(request, "rebanho/animal_lista.html", {
        "animais": animais,
        "lotes": Lote.objects.all(),
        "filtros": request.GET,
        # Ordenar não conta como filtro: só os campos que reduzem a lista.
        "filtros_ativos": any(request.GET.get(c) for c in
                              ("q", "categoria", "situacao", "dias_min", "dias_max",
                               "lote", "cor", "baixados")),
        "querystring": parametros.urlencode(),
        "cabecalhos": cols.cabecalhos(chave, sentido),
        "categorias": [("LACTACAO", "Em lactação"), ("SECA", "Seca"), ("NOVILHA", "Novilha"),
                       ("BEZERRA", "Bezerra")],
        "situacoes": [("VAZIA", "Vazia"), ("INSEMINADA", "Inseminada"), ("PRENHE", "Prenhe")],
        "cores": [("padrao", "Cor padrão")] + [(c, r) for c, r, _ in tema.CORES_BRINCO],
    })


@login_required
def animal_detalhe(request, pk):
    animais, config = carregar_animais(Animal.objects.filter(pk=pk))
    if not animais:
        return redirect("animal_lista")
    animal = animais[0]
    eventos = sorted(animal.eventos.all(), key=lambda e: (e.data, e.id), reverse=True)
    form = EventoForm(initial={"animal": animal})
    form.fields["animal"].widget = forms.HiddenInput()
    return render(request, "rebanho/animal_detalhe.html", {
        "animal": animal, "s": animal.status, "eventos": eventos, "form": form, "config": config,
        "filhas": animal.filhas.all(),
        "pesagens": list(animal.pesagens.all()),
        "form_peso": PesagemForm(initial={"animal": animal}),
    })


@login_required
def animal_form(request, pk=None):
    animal = get_object_or_404(Animal, pk=pk) if pk else None
    form = AnimalForm(request.POST or None, instance=animal)
    if request.method == "POST" and form.is_valid():
        animal = form.save()
        messages.success(request, f"Animal {animal.brinco} salvo.")
        return redirect("animal_detalhe", pk=animal.pk)
    return render(request, "rebanho/form.html", {
        "form": form,
        "titulo": f"Editar {animal}" if animal else "Cadastrar animal",
        "botao": "Salvar animal",
        "voltar": animal and animal.pk,
    })


@login_required
def evento_novo(request):
    initial = {k: request.GET[k] for k in ("animal", "tipo") if k in request.GET}
    form = EventoForm(request.POST or None, initial=initial)
    if request.method == "POST":
        if form.is_valid():
            evento = form.save()
            if evento.tipo in ("VENDA", "MORTE"):
                Animal.objects.filter(pk=evento.animal_id).update(ativo=False)
            messages.success(request, f"Evento registrado: {evento.get_tipo_display().lower()} da {evento.animal.brinco}.")
            destino = request.POST.get("proximo")
            if destino == "painel":
                return redirect("painel")
            return redirect("animal_detalhe", pk=evento.animal_id)
        # Se veio da ficha do animal, volta para lá mostrando os erros
        if request.POST.get("proximo") == "animal" and request.POST.get("animal"):
            for campo, erros in form.errors.items():
                for erro in erros:
                    messages.error(request, erro)
            return redirect("animal_detalhe", pk=request.POST["animal"])
    proximo = request.POST.get("proximo") or request.GET.get("proximo") or "ficha"
    return render(request, "rebanho/evento_form.html", {"form": form, "proximo": proximo})


@login_required
def evento_excluir(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    animal = evento.animal
    if request.method == "POST":
        tipo = evento.get_tipo_display()
        evento.delete()
        if not animal.eventos.filter(tipo__in=("VENDA", "MORTE")).exists():
            Animal.objects.filter(pk=animal.pk).update(ativo=True)
        messages.success(request, f"Evento “{tipo}” excluído. As previsões foram recalculadas.")
    return redirect("animal_detalhe", pk=animal.pk)


class ConfiguracaoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoReprodutiva
        fields = "__all__"


@login_required
def configuracao(request):
    form = ConfiguracaoForm(request.POST or None, instance=ConfiguracaoReprodutiva.atual())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Parâmetros salvos. Todas as listas já usam os novos valores.")
        return redirect("painel")
    return render(request, "rebanho/form.html", {
        "form": form, "titulo": "Parâmetros reprodutivos", "botao": "Salvar parâmetros",
    })


# --------------------------------------------------------------------------
# Aparência (tema por usuário)
# --------------------------------------------------------------------------

class AparenciaForm(forms.ModelForm):
    class Meta:
        model = PreferenciasVisuais
        fields = ["cor_principal", "cor_brinco", "cor_fundo"]

    def clean(self):
        dados = super().clean()
        for campo in self.Meta.fields:
            if dados.get(campo):
                dados[campo] = dados[campo].upper()
        return dados


def _tema_das_cores(principal, brinco, fundo):
    for chave, (_, p, b, f) in tema.TEMAS.items():
        if (p, b, f) == (principal.upper(), brinco.upper(), fundo.upper()):
            return chave
    return "personalizado"


@login_required
def aparencia(request):
    prefs = PreferenciasVisuais.objects.filter(usuario=request.user).first() \
        or PreferenciasVisuais(usuario=request.user)

    if request.method == "POST" and "restaurar" in request.POST:
        if prefs.pk:
            prefs.delete()
        messages.success(request, "Aparência restaurada para o tema padrão.")
        return redirect("aparencia")

    form = AparenciaForm(request.POST or None, instance=prefs)
    if request.method == "POST" and form.is_valid():
        prefs = form.save(commit=False)
        prefs.tema = _tema_das_cores(prefs.cor_principal, prefs.cor_brinco, prefs.cor_fundo)
        prefs.save()
        messages.success(request, "Aparência salva.")
        return redirect("aparencia")

    temas = [
        {"chave": k, "nome": n, "principal": p, "brinco": b, "fundo": f,
         "texto_brinco": tema.texto_para(b), "texto_fundo": tema.texto_para(f)}
        for k, (n, p, b, f) in tema.TEMAS.items()
    ]
    return render(request, "rebanho/aparencia.html", {
        "form": form, "temas": temas, "tema_atual": prefs.tema if prefs.pk else tema.TEMA_PADRAO,
        "cores_brinco": tema.CORES_BRINCO,
    })


@login_required
def aparencia_previa(request):
    """Devolve o CSS de um tema sem salvar, para a prévia ao vivo."""
    try:
        css = tema.css_tema(
            request.GET.get("principal", "").upper(),
            request.GET.get("brinco", "").upper(),
            request.GET.get("fundo", "").upper(),
        )
    except ValueError as erro:
        return HttpResponse(str(erro), status=400, content_type="text/plain; charset=utf-8")
    return HttpResponse(css, content_type="text/css; charset=utf-8")


@login_required
def pesagem_nova(request):
    form = PesagemForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            pesagem = form.save()
            messages.success(request, f"Peso de {pesagem.peso} kg registrado para "
                                      f"{pesagem.animal.brinco}.")
            return redirect("animal_detalhe", pk=pesagem.animal_id)
        for erros in form.errors.values():
            for erro in erros:
                messages.error(request, erro)
        if request.POST.get("animal", "").isdigit():
            return redirect("animal_detalhe", pk=request.POST["animal"])
    return redirect("animal_lista")


@login_required
def pesagem_excluir(request, pk):
    pesagem = get_object_or_404(Pesagem, pk=pk)
    animal_id = pesagem.animal_id
    if request.method == "POST":
        pesagem.delete()
        messages.success(request, "Pesagem excluída.")
    return redirect("animal_detalhe", pk=animal_id)
