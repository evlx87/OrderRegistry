from django import forms
from .models import Order

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__'
        widgets = {
            'issue_date': forms.DateInput(attrs={
                'type': 'date',
            }),
        }

    def clean_issue_date(self):
        """Проверяем, если дата не указана, оставляем старую."""
        issue_date = self.cleaned_data.get('issue_date')
        if not issue_date:
            instance = getattr(self, 'instance', None)
            if instance and instance.pk:
                issue_date = instance.issue_date
        return issue_date