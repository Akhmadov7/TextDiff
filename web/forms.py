from django import forms


class TaskForm(forms.Form):
    name = forms.CharField(label="Название", max_length=200)
    file = forms.FileField(label="CSV-файл", help_text="Обязательные колонки: text и group")
    text_col = forms.CharField(label="Колонка с текстом", initial="text", max_length=100)
    group_col = forms.CharField(label="Колонка с группой", initial="group", max_length=100)
    test = forms.ChoiceField(
        label="Статистический тест",
        choices=[("mannwhitney", "Манна—Уитни"), ("ttest", "t-критерий")],
        initial="mannwhitney",
    )
    top_n = forms.IntegerField(label="Топ слов", initial=20, min_value=1, max_value=200)

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if not uploaded.name.lower().endswith(".csv"):
            raise forms.ValidationError("Нужен CSV-файл с расширением .csv")
        if uploaded.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Файл не должен быть больше 10 МБ")
        return uploaded
