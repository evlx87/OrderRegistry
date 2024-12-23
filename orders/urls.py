from django.urls import path

from orders.views import IndexView, AddOrderView, ExportToExcelView, EditOrderView, DeleteOrderView

app_name='orders'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('add_order/', AddOrderView.as_view(), name='add_order'),
    path('<int:pk>/edit_order/', EditOrderView.as_view(), name='edit_order'),
    path('<int:pk>/delete_order/', DeleteOrderView.as_view(), name='delete_order'),
    path('export_to_excel/', ExportToExcelView.as_view(), name='export_to_excel'),
]