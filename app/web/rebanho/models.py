from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from . import tema as temas

validar_cor = RegexValidator(temas.HEX_RE, "Use uma cor no formato #RRGGBB.")


class ConfiguracaoReprodutiva(models.Model):
    """Parâmetros usados nos cálculos. Existe só um registro (id=1)."""

    periodo_voluntario_espera = models.PositiveIntegerField(
        "Período voluntário de espera (dias pós-parto)", default=50
    )
    duracao_ciclo = models.PositiveIntegerField("Duração do ciclo estral (dias)", default=21)
    retorno_cio_inicio = models.PositiveIntegerField(
        "Observar retorno ao cio a partir de (dias após IA)", default=18
    )
    retorno_cio_fim = models.PositiveIntegerField(
        "Observar retorno ao cio até (dias após IA)", default=24
    )
    dias_diagnostico = models.PositiveIntegerField(
        "Diagnóstico de gestação (dias após IA)", default=30
    )
    dias_gestacao = models.PositiveIntegerField(
        "Duração da gestação (dias)", default=0,
        help_text="Deixe 0 para usar a média da raça de cada animal "
                  "(Holandesa 280, Jersey 279, Girolando 285, Gir e Pardo-Suíço 290).",
    )
    dias_secagem = models.PositiveIntegerField("Secar (dias antes do parto)", default=60)
    dias_pre_parto = models.PositiveIntegerField("Pré-parto (dias antes do parto)", default=21)
    idade_minima_novilha = models.PositiveIntegerField(
        "Idade mínima da novilha para 1ª IA (meses)", default=14
    )
    alerta_sem_cio = models.PositiveIntegerField(
        "Alerta de vaca sem cio (dias pós-parto)", default=90
    )
    alerta_repetidora = models.PositiveIntegerField(
        "Alerta de repetição de cio (nº de IAs sem prenhez)", default=3
    )
    antecedencia_alertas = models.PositiveIntegerField(
        "Antecedência dos alertas de secagem e pré-parto (dias)", default=7
    )

    class Meta:
        verbose_name = "configuração reprodutiva"
        verbose_name_plural = "configuração reprodutiva"

    def __str__(self):
        return "Parâmetros reprodutivos"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def atual(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Lote(models.Model):
    nome = models.CharField(max_length=60, unique=True)
    descricao = models.CharField("descrição", max_length=200, blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Touro(models.Model):
    nome = models.CharField(max_length=80)
    codigo = models.CharField("código / registro", max_length=40, blank=True)
    raca = models.CharField("raça", max_length=40, blank=True)
    central = models.CharField("central de sêmen", max_length=80, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.codigo})" if self.codigo else self.nome


class Animal(models.Model):
    class Raca(models.TextChoices):
        HOLANDESA = "HOL", "Holandesa"
        JERSEY = "JER", "Jersey"
        GIROLANDO = "GIROL", "Girolando"
        GIR = "GIR", "Gir Leiteiro"
        PARDO = "PS", "Pardo-Suíço"
        OUTRA = "OUT", "Outra / mestiça"

    brinco = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=60, blank=True)
    raca = models.CharField("raça", max_length=6, choices=Raca.choices, default=Raca.GIROLANDO)
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)
    mae = models.ForeignKey(
        "self", verbose_name="mãe", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="filhas",
    )
    pai = models.ForeignKey(
        Touro, verbose_name="pai (touro)", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="filhas",
    )
    lote = models.ForeignKey(Lote, null=True, blank=True, on_delete=models.SET_NULL)
    cor_brinco = models.CharField(
        "cor do brinco", max_length=10, blank=True,
        choices=[(c, rotulo) for c, rotulo, _ in temas.CORES_BRINCO],
        help_text="A mesma cor do brinco físico. Deixe em branco para usar a cor padrão do tema.",
    )
    lactacoes_anteriores = models.PositiveIntegerField(
        "lactações anteriores à importação", default=0,
        help_text="Partos que aconteceram antes de o animal entrar no sistema. Somado à contagem "
                  "de partos registrados, dá o número da lactação atual.",
    )
    ativo = models.BooleanField(default=True, help_text="Desmarcado após venda ou morte.")
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name_plural = "animais"
        ordering = ["brinco"]

    def __str__(self):
        return f"{self.brinco} – {self.nome}" if self.nome else self.brinco

    @property
    def peso_atual(self):
        """Última pesagem registrada, ou None."""
        pesagens = list(self.pesagens.all())
        return pesagens[0] if pesagens else None

    @property
    def ganho_diario(self):
        """Ganho médio de peso por dia (kg/dia) entre a primeira e a última pesagem."""
        pesagens = sorted(self.pesagens.all(), key=lambda p: p.data)
        if len(pesagens) < 2:
            return None
        dias = (pesagens[-1].data - pesagens[0].data).days
        if dias <= 0:
            return None
        return round(float(pesagens[-1].peso - pesagens[0].peso) / dias, 2)

    @property
    def classe_brinco(self):
        return f"cor-{self.cor_brinco}" if self.cor_brinco else ""

    @property
    def status(self):
        """Situação reprodutiva calculada a partir dos eventos (ver reproducao.py)."""
        if not hasattr(self, "_status_cache"):
            from .reproducao import calcular_status
            self._status_cache = calcular_status(self)
        return self._status_cache


class Pesagem(models.Model):
    """Histórico de peso. Usado sobretudo em bezerras e novilhas, para acompanhar o ganho
    de peso diário e saber quando a novilha atinge o peso de cobertura."""

    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name="pesagens")
    data = models.DateField()
    peso = models.DecimalField("peso (kg)", max_digits=6, decimal_places=1)
    observacoes = models.CharField("observações", max_length=255, blank=True)

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "pesagem"
        verbose_name_plural = "pesagens"
        constraints = [models.UniqueConstraint(fields=["animal", "data"],
                                               name="uma_pesagem_por_animal_por_dia")]

    def __str__(self):
        return f"{self.animal.brinco}: {self.peso} kg em {self.data:%d/%m/%Y}"


class Evento(models.Model):
    class Tipo(models.TextChoices):
        PARTO = "PARTO", "Parto"
        CIO = "CIO", "Cio observado"
        INSEMINACAO = "IA", "Inseminação"
        DIAGNOSTICO = "DG", "Diagnóstico de gestação"
        ABORTO = "ABORTO", "Aborto"
        SECAGEM = "SECAGEM", "Secagem"
        VENDA = "VENDA", "Venda"
        MORTE = "MORTE", "Morte"

    class Resultado(models.TextChoices):
        POSITIVO = "POS", "Prenhe"
        NEGATIVO = "NEG", "Vazia"

    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name="eventos")
    tipo = models.CharField(max_length=8, choices=Tipo.choices)
    data = models.DateField()
    touro = models.ForeignKey(
        Touro, null=True, blank=True, on_delete=models.SET_NULL,
    )
    inseminador = models.CharField(max_length=60, blank=True)
    resultado = models.CharField(
        max_length=3, choices=Resultado.choices, blank=True,
    )
    observacoes = models.CharField("observações", max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["data", "id"]
        indexes = [models.Index(fields=["animal", "data"])]

    def __str__(self):
        return f"{self.animal.brinco} · {self.get_tipo_display()} em {self.data:%d/%m/%Y}"


class PreferenciasVisuais(models.Model):
    """Cores escolhidas por cada usuário. O resto do tema é derivado em tema.py."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferencias_visuais"
    )
    tema = models.CharField(max_length=20, default=temas.TEMA_PADRAO,
                            help_text="Tema pronto de origem, ou 'personalizado'.")
    cor_principal = models.CharField(max_length=7, validators=[validar_cor],
                                     default=temas.TEMAS[temas.TEMA_PADRAO][1])
    cor_brinco = models.CharField(max_length=7, validators=[validar_cor],
                                  default=temas.TEMAS[temas.TEMA_PADRAO][2])
    cor_fundo = models.CharField(max_length=7, validators=[validar_cor],
                                 default=temas.TEMAS[temas.TEMA_PADRAO][3])

    class Meta:
        verbose_name = "preferências visuais"
        verbose_name_plural = "preferências visuais"

    def __str__(self):
        return f"Aparência de {self.usuario}"

    def css(self):
        return temas.css_tema(self.cor_principal, self.cor_brinco, self.cor_fundo)
