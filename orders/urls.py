from django.urls import path

from orders.views import IndexView, add_order

app_name='orders'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('add_order/', add_order, name='add_order'),
]