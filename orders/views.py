from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView

from orders.forms import OrderForm
from orders.models import Order


# Create your views here.
class IndexView(ListView):
    model = Order
    template_name = 'orders/index.html'
    context_object_name = 'orders'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Приказы'
        return context


def add_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Приказ успешно добавлен!')
            return redirect(reverse_lazy('orders:index'))  # Переход на страницу списка приказов после успешного сохранения
    else:
        form = OrderForm()

    context = {'form': form}
    return render(request, 'orders/add_order.html', context)