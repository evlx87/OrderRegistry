from django import forms
from .models import Order


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'document_number',
            'issue_date',
            'document_title',
            'signed_by',
            'responsible_executor',
            'transferred_to_execution',
            'transferred_for_storage',
            'heraldic_blank_number',
            'note',
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
        }
