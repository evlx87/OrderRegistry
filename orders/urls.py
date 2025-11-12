from django.urls import path

from orders.views import IndexView, AddOrderView, ExportToExcelView, OrderDetailView, OrderEditView, DeleteOrderView, \
    log_cancel_action, log_ui_click

app_name='orders'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('add_order/', AddOrderView.as_view(), name='add_order'),
    path('<int:pk>/detail_order/', OrderDetailView.as_view(), name='detail_order'),
    path('<int:pk>/edit_order/', OrderEditView.as_view(), name='edit_order'),
    path('<int:pk>/delete_order/', DeleteOrderView.as_view(), name='delete_order'),
    path('export_to_excel/', ExportToExcelView.as_view(), name='export_to_excel'),
    path('log_action/cancel/', log_cancel_action, name='log_cancel'),
    path('log_action/ui_click/', log_ui_click, name='log_ui_click'),
]