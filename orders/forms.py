from django import forms

from .models import Order


class OrderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Итерация по всем полям для добавления класса Bootstrap
        for field_name, field in self.fields.items():

            # Пропускаем поля, которые требуют специального класса (например,
            # Checkbox)
            if field_name == 'is_active':
                field.widget.attrs['class'] = 'form-check-input'
                continue

            # Добавляем класс 'form-control' ко всем остальным полям
            current_classes = field.widget.attrs.get('class', '')
            if 'form-control' not in current_classes:
                field.widget.attrs['class'] = current_classes + \
                    (' form-control' if current_classes else 'form-control')

    class Meta:
        model = Order
        fields = '__all__'
        widgets = {
            'issue_date': forms.DateInput(attrs={
                'type': 'date',
            }),
            # Дополнительный виджет для файла (если есть)
            'scan': forms.FileInput(attrs={}),
            # Виджет для чекбокса
            'is_active': forms.CheckboxInput(attrs={}),
        }

    def clean_issue_date(self):
        """Проверяем, если дата не указана, оставляем старую."""
        issue_date = self.cleaned_data.get('issue_date')
        if not issue_date:
            instance = getattr(self, 'instance', None)
            if instance and instance.pk:
                issue_date = instance.issue_date
        return issue_date
