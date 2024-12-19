from django.urls import path

from orders.views import IndexView, AddOrderView, ExportToExcelView

app_name='orders'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('add_order/', AddOrderView.as_view(), name='add_order'),
    path('export_to_excel/', ExportToExcelView.as_view(), name='export_to_excel'),
]