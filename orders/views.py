from datetime import date

import openpyxl
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from orders.forms import OrderForm
from orders.models import Order


# Create your views here.
EXPORT_FIELD_MAP = {
    'document_number': 'Номер документа',
    'issue_date': 'Дата издания',
    'document_title': 'Наименование документа',
    'signed_by': 'Подписант',
    'responsible_executor': 'Ответственный исполнитель',
    'transferred_to_execution': 'Передан на исполнение',
    'transferred_for_storage': 'Передан на хранение',
    'heraldic_blank_number': 'Номер геральдического бланка',
    'note': 'Примечание'
}

class OrderQuerysetMixin:
    """
    Этот Mixin содержит логику для фильтрации и поиска queryset'а.
    Мы будем использовать его в IndexView и ExportToExcelView,
    чтобы экспорт соответствовал тому, что видит пользователь.
    """
    def get_filtered_queryset(self, request):
        queryset = Order.objects.all() # Начинаем с .all()
        search = request.GET.get("search")
        # Мы ищем 'filter_year' (с формы) или 'year' (с модального окна экспорта)
        year = request.GET.get('filter_year') or request.GET.get('year')
        filter_doc_num = request.GET.get("filter_doc_num")
        filter_doc_type = request.GET.get("filter_doc_type")

        if year:
            try:
                year_int = int(year)
                queryset = queryset.filter(issue_date__year=year_int)
            except (ValueError, TypeError):
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

        if filter_doc_type:
            queryset = queryset.filter(doc_type=filter_doc_type)
        
        # Если не было поиска, сортируем по ID. 
        # Если был поиск, сортировка 'rank' уже применена.
        if not search:
            queryset = queryset.order_by('-id')

        return queryset


class IndexView(OrderQuerysetMixin, ListView):
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
        # Всю логику переносим в Mixin
        return self.get_filtered_queryset(self.request)
        
        # queryset = super().get_queryset()
        # queryset = queryset.filter(pk__isnull=False)
        # search = self.request.GET.get("search")
        # year = self.request.GET.get('year')
        # filter_doc_num = self.request.GET.get("filter_doc_num")

        # if year:
        #     try:
        #         year_int = int(year)
        #         queryset = queryset.filter(issue_date__year=year_int)
        #     except ValueError:
        #         pass

        # if search:
        #     query = SearchQuery(search, search_type='websearch')
        #     vector = SearchVector('document_title')
        #     queryset = queryset.annotate(
        #         rank=SearchRank(vector, query)
        #     ).filter(rank__gte=0.01).order_by('-rank', '-issue_date')

        # if filter_doc_num:
        #     queryset = queryset.filter(
        #         document_number__icontains=filter_doc_num)

        # return queryset.order_by('-id') if not search else queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Приказы'
        # Получаем параметры фильтра для передачи в <input type="hidden">
        context["search"] = self.request.GET.get("search", "")
        context["filter_doc_num"] = self.request.GET.get("filter_doc_num", "")
        context["selected_year"] = self.request.GET.get("filter_year", date.today().year)

        context["years"] = self.get_year_choices()

        context['order_form'] = OrderForm()
        context['login_form'] = AuthenticationForm()
        # Добавляем карту полей в контекст для модального окна
        context['export_field_map'] = EXPORT_FIELD_MAP

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
    template_name = 'orders/includes/inc__modal_delete_order.html'
    success_url = reverse_lazy('orders:index')
    success_message = 'Приказ успешно удален.'

    # Этот метод будет обрабатывать GET-запрос (загрузку формы в модалку)
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return render(request, self.template_name, context)

    # Этот метод будет обрабатывать POST-запрос (нажатие "Да, удалить")
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()

        # Проверяем, является ли запрос AJAX
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Отправляем JSON-ответ об успехе
            return JsonResponse({'success': True, 'redirect_url': success_url})
        else:
            # Стандартное поведение, если AJAX не используется
            return HttpResponseRedirect(success_url)


class ExportToExcelView(OrderQuerysetMixin, View): # <-- Добавляем Mixin

    def get(self, request, *args, **kwargs):
        
        # 1. Получаем список выбранных полей из GET-параметров
        selected_fields = request.GET.getlist('fields')

        # 2. Валидация: если полей не выбрано или кто-то подделал запрос
        if not selected_fields:
            # (Здесь можно вернуть красивую страницу ошибки, но пока так)
            return HttpResponse("Ошибка: не выбрано ни одного поля для экспорта.", status=400)

        # 3. Фильтруем queryset, используя ту же логику, что и IndexView
        # Mixin автоматически прочитает 'search', 'year' и т.д. из request.GET
        queryset = self.get_filtered_queryset(request)

        # 4. Формируем заголовки и список полей для запроса
        headers = []
        valid_field_names = []
        
        # Используем .items() для сохранения порядка (в Python 3.7+)
        for field_name, field_label in EXPORT_FIELD_MAP.items():
            if field_name in selected_fields:
                headers.append(field_label)
                valid_field_names.append(field_name)
        
        # 5. Оптимизированный запрос к БД
        # values_list() возьмет только те поля, которые выбрал пользователь
        orders_data = queryset.values_list(*valid_field_names)

        # 6. Создание файла Excel
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        
        # Добавляем динамические заголовки
        sheet.append(headers)

        # 7. Обработка данных
        for order_tuple in orders_data:
            row = list(order_tuple)
            
            # Ищем, есть ли в наших данных даты (объекты date)
            for i, value in enumerate(row):
                if isinstance(value, date):
                    # Форматируем дату в привычный вид
                    row[i] = value.strftime('%d.%m.%Y')
                elif value is None:
                    row[i] = '' # Заменяем None на пустые строки
            
            sheet.append(row)

        # 8. Подготовка ответа
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=orders_export.xlsx'
        workbook.save(response)

        return response
