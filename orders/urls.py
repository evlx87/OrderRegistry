from django.urls import path

from orders.views import IndexView

app_name='orders'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
]