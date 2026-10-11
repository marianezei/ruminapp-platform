from datetime import date

from django import forms

from .models import Animal, Evento, Pesagem, Touro
from .reproducao import calcular_status


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class AnimalForm(forms.ModelForm):
    class Meta:
        model = Animal
        fields = ["brinco", "cor_brinco", "nome", "raca", "data_nascimento", "lote", "mae", "pai",
                  "observacoes"]
        widgets = {
            "data_nascimento": DateInput(),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
            "cor_brinco": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cor_brinco"].choices = [("", "Padrão")] + list(self.fields["cor_brinco"].choices)[1:]


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ["animal", "tipo", "data", "touro", "inseminador", "resultado", "observacoes"]
        widgets = {"data": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["animal"].queryset = Animal.objects.filter(ativo=True)
        self.fields["touro"].queryset = Touro.objects.filter(ativo=True)
        if not self.initial.get("data"):
            self.initial["data"] = date.today()

    def clean(self):
        dados = super().clean()
        animal, tipo, data = dados.get("animal"), dados.get("tipo"), dados.get("data")
        if not (animal and tipo and data):
            return dados

        if data > date.today():
            self.add_error("data", "A data não pode estar no futuro.")
            return dados

        # Situação da vaca na data do evento (considerando só eventos anteriores)
        s = calcular_status(animal, hoje=data, ate=data)

        if s.categoria == "BAIXA":
            raise forms.ValidationError("Este animal já foi baixado (venda ou morte).")

        if tipo == "IA":
            if s.situacao == "PRENHE":
                self.add_error("tipo", "A vaca está com prenhez confirmada nessa data. "
                                       "Registre um aborto ou diagnóstico negativo antes.")
            if s.categoria == "BEZERRA":
                self.add_error("animal", "Animal com menos de 12 meses.")
        if tipo == "DG":
            if not dados.get("resultado"):
                self.add_error("resultado", "Informe se a vaca está prenhe ou vazia.")
            if s.situacao != "INSEMINADA":
                self.add_error("tipo", "Só dá para diagnosticar uma vaca que foi inseminada e ainda "
                                       "não tem diagnóstico.")
        if tipo == "SECAGEM" and s.categoria != "LACTACAO":
            self.add_error("tipo", "Só vacas em lactação podem ser secas.")
        if tipo == "ABORTO" and s.situacao != "PRENHE":
            self.add_error("tipo", "Aborto só pode ser registrado em vaca prenhe.")

        # Limpa campos que não se aplicam ao tipo escolhido
        if tipo != "IA":
            dados["touro"] = None
            dados["inseminador"] = ""
        if tipo != "DG":
            dados["resultado"] = ""
        return dados


class PesagemForm(forms.ModelForm):
    class Meta:
        model = Pesagem
        fields = ["animal", "data", "peso", "observacoes"]
        widgets = {"data": DateInput(), "animal": forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["peso"].widget.attrs.update({"step": "0.1", "min": "1", "max": "1500",
                                                 "inputmode": "decimal"})
        if not self.initial.get("data"):
            self.initial["data"] = date.today()

    def clean_data(self):
        data = self.cleaned_data["data"]
        if data > date.today():
            raise forms.ValidationError("A data da pesagem não pode estar no futuro.")
        return data

    def clean(self):
        dados = super().clean()
        animal, data, peso = dados.get("animal"), dados.get("data"), dados.get("peso")
        if animal and data:
            if animal.data_nascimento and data < animal.data_nascimento:
                self.add_error("data", "A pesagem é anterior ao nascimento do animal.")
            existente = Pesagem.objects.filter(animal=animal, data=data)
            if self.instance.pk:
                existente = existente.exclude(pk=self.instance.pk)
            if existente.exists():
                self.add_error("data", f"{animal.brinco} já tem uma pesagem registrada nessa data.")
        if peso is not None and not (1 <= peso <= 1500):
            self.add_error("peso", "Informe um peso entre 1 e 1500 kg.")
        return dados
