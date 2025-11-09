from datetime import date

import openpyxl
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

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
        queryset = queryset.filter(pk__isnull=False)
        search = self.request.GET.get("search")
        year = self.request.GET.get('year')
        filter_doc_num = self.request.GET.get("filter_doc_num")

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
        context["selected_year"] = self.request.GET.get("filter_year", date.today().year)
        context['order_form'] = OrderForm()
        context['login_form'] = AuthenticationForm()
        return context


class AddOrderView(SuccessMessageMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'orders/add_order.html'
    success_url = reverse_lazy('orders:index')
    # success_message = 'Приказ успешно добавлен!'
    def form_valid(self, form):
        form.instance.author = self.request.user
        # Вызываем родительский метод, но пока не возвращаем его
        response = super().form_valid(form)

        # Проверяем, это AJAX-запрос?
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Если да, возвращаем JSON об успехе
            return JsonResponse({'success': True})
        else:
            # Если нет (обычная отправка), возвращаем редирект
            return response

    def form_invalid(self, form):
        # Проверяем, это AJAX-запрос?
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Если да, возвращаем JSON с ошибками валидации
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        else:
            # Если нет, рендерим страницу с формой и ошибками
            return super().form_invalid(form)


class OrderDetailView(DetailView):
    model = Order
    # Используем новый шаблон для деталей
    template_name = 'orders/includes/inc__modal_order_detail.html'
    context_object_name = 'order'

    # DetailView по умолчанию возвращает HTTP-ответ.
    # Если вы используете AJAX, вам, возможно, не нужны изменения в этом классе,
    # если ваш код JS обрабатывает форму, как показано выше.
    # Если вы используете просто render(request, '...', context), то это то же самое.


class OrderEditView(UpdateView):
    model = Order
    # Используем модифицированный шаблон для редактирования
    template_name = 'orders/includes/inc__modal_edit_order.html'
    form_class = OrderForm
    context_object_name = 'order'

    # Переопределяем метод для обработки AJAX-запросов и частичной загрузки шаблона
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return render(request, self.template_name, self.get_context_data(form=form))

    def form_valid(self, form):
        # При успешном сохранении возвращаем пустой ответ или JSON (для AJAX)
        form.save()
        return render(self.request, 'orders/empty.html')  # Возвращаем пустой шаблон или HTTP 204

    def form_invalid(self, form):
        # При ошибках валидации возвращаем шаблон формы, чтобы она отобразилась в модальном окне
        return render(self.request, self.template_name, self.get_context_data(form=form))


class DeleteOrderView(DeleteView):
    model = Order
    template_name = 'orders/delete_order.html'
    success_url = reverse_lazy('orders:index')
    success_message = 'Приказ успешно удален.'

    # def delete(self, request, *args, **kwargs):
    #     obj = self.get_object_or_404(*args, **kwargs)
    #     if obj:
    #         obj.delete()
    #         messages.success(self.request, 'Приказ удален.')
    #     else:
    #         messages.error(self.request, 'Приказ не найден.')
    #     return redirect(self.success_url)
    #
    # def get_object_or_404(self, queryset, *args, **kwargs):
    #     try:
    #         return self.get_object(queryset, *args, **kwargs)
    #     except Http404:
    #         raise Http404('Object does not exist.')


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
