from datetime import datetime

import openpyxl
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.cache import cache
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from orders.forms import OrderForm
from orders.models import Order


# Create your views here.
class IndexView(ListView):
    model = Order
    template_name = 'orders/index.html'
    context_object_name = 'orders'

    def get_year_choices(self):
        years_cache_key = 'order_years_list'
        years_list = cache.get(years_cache_key)

        if years_list is None:
            # Выполняем запрос только если его нет в кеше
            years = Order.objects.dates('issue_date', 'year', order='ASC')
            years_list = [(year.year, year.year) for year in years]

            # Сохраняем результат в кеше на 1 час (3600 секунд)
            cache.set(years_cache_key, years_list, timeout=3600)

        return years_list

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get("search")
        filter_doc_num = self.request.GET.get("filter_doc_num")
        year = self.request.GET.get('year')

        if year:
            try:
                year_int = int(year)
                queryset = queryset.filter(issue_date__year=year_int)
            except ValueError:
                pass

        if search:
            query = SearchQuery(search, search_type='websearch')
            vector = SearchVector('document_title')
            queryset = queryset.annotate(
                rank=SearchRank(vector, query)
            ).filter(rank__gte=0.01).order_by('-rank', '-issue_date')

        if filter_doc_num:
            queryset = queryset.filter(
                document_number__icontains=filter_doc_num)

        return queryset.order_by('-id') if not search else queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Приказы'
        context["search"] = self.request.GET.get("search", "")
        context["filter_doc_num"] = self.request.GET.get("filter_doc_num", "")
        context["years"] = self.get_year_choices()
        context["selected_year"] = self.request.GET.get(
            "filter_year", datetime.date.today().year)
        return context


class AddOrderView(SuccessMessageMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'orders/add_order.html'
    success_url = reverse_lazy('orders:index')
    success_message = 'Приказ успешно добавлен!'


class EditOrderView(SuccessMessageMixin, UpdateView):
    model = Order
    template_name = 'orders/edit_order.html'
    form_class = OrderForm
    success_url = reverse_lazy('orders:index')
    success_message = 'Приказ успешно обновлён!'

    def get_object(self, queryset=None, *args, **kwargs):
        obj = super().get_object(queryset, *args, **kwargs)
        if not obj:
            raise Http404('Object does not exist.')
        return obj

    def form_invalid(self, form):
        for error in form.errors.values():
            for message in error:
                self.request._messages.add(message.level, message)
        return super().form_invalid(form)

    def form_valid(self, form):
        # Получаем текущий объект приказа
        order = self.object

        # Если дата не указана, оставляем ту, которая была до этого
        if not form.cleaned_data['issue_date']:
            order.issue_date = order.issue_date

        # Сохраняем изменения
        order.save()

        return HttpResponseRedirect(self.get_success_url())


class DeleteOrderView(DeleteView):
    model = Order
    template_name = 'orders/delete_order.html'
    success_url = reverse_lazy('orders:index')

    def delete(self, request, *args, **kwargs):
        obj = self.get_object_or_404(*args, **kwargs)
        if obj:
            obj.delete()
            messages.success(self.request, 'Приказ удален.')
        else:
            messages.error(self.request, 'Приказ не найден.')
        return redirect(self.success_url)

    def get_object_or_404(self, queryset, *args, **kwargs):
        try:
            return self.get_object(queryset, *args, **kwargs)
        except Http404:
            raise Http404('Object does not exist.')


class ExportToExcelView(View):
    def get(self, request, *args, **kwargs):
        # 1. Определение полей для выборки и заголовков
        field_names = [
            'document_number', 'issue_date', 'document_title', 'signed_by',
            'responsible_executor', 'transferred_to_execution',
            'transferred_for_storage', 'heraldic_blank_number', 'note'
        ]

        headers = [
            'Номер документа', 'Дата издания', 'Наименование документа',
            'Подписант', 'Ответственный исполнитель', 'Передан на исполнение',
            'Передан на хранение', 'Номер геральдического бланка', 'Примечание'
        ]

        # 2. ОПТИМИЗИРОВАННЫЙ ЗАПРОС (Шаг 5)
        # Получаем только необходимые значения, а не полные объекты модели
        orders_data = Order.objects.order_by('-id').values_list(*field_names)

        data = [headers]

        # 3. Обработка данных
        for order_tuple in orders_data:
            order_list = list(order_tuple)

            # Индекс 1 соответствует issue_date
            issue_date = order_list[1]

            # ИСПРАВЛЕНИЕ БАГА: Проверка на None/Null (Шаг 2)
            # Форматируем дату или оставляем пустую строку
            if issue_date:
                # issue_date - это объект datetime.date или datetime.datetime
                order_list[1] = issue_date.strftime('%d.%m.%Y')
            else:
                order_list[1] = ''

            data.append(order_list)

        # 4. Создание файла Excel
        workbook = openpyxl.Workbook()
        sheet = workbook.active

        for row in data:
            sheet.append(row)

        # 5. Подготовка ответа
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=orders.xlsx'
        workbook.save(response)

        return response
