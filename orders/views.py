import logging
from datetime import date

import openpyxl
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.cache import cache
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from orders.forms import OrderForm
from orders.models import Order

# Create your views here.
# --- Настройка логгеров ---
# Используем логгер для действий пользователя (Успех/Провал)
action_logger = logging.getLogger('user_actions_logger')
# Используем логгер для критических ошибок (Ошибки сервера)
error_logger = logging.getLogger('orders')

EXPORT_FIELD_MAP = {
    'doc_type': 'Вид документа',
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


def log_cancel_action(request):
    """Принимает AJAX-запрос, логирует отмену и возвращает пустой ответ."""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Получаем тип формы, из которой была отменена операция
        form_type = request.GET.get('form_type', 'Неизвестная')

        action_logger.info(
            f"ОТМЕНА: Пользователь '{request.user.username}' нажал 'Отмена' "
            f"в модальном окне: {form_type}."
        )
        return JsonResponse({'status': 'logged'})

    return JsonResponse({'status': 'not logged'}, status=400)


class OrderQuerysetMixin:
    """
    Этот Mixin содержит логику для фильтрации и поиска queryset'а.
    Мы будем использовать его в IndexView и ExportToExcelView,
    чтобы экспорт соответствовал тому, что видит пользователь.
    """

    def get_filtered_queryset(self, request):
        queryset = Order.objects.all()
        search = request.GET.get("search")
        year = request.GET.get('filter_year') or request.GET.get('year')
        filter_doc_num = request.GET.get("filter_doc_num")
        doc_type = request.GET.get(
            "filter_doc_type") or request.GET.get("doc_type")

        search_query_param = request.GET.get('q')

        if search_query_param:
            # --- ЛОГИРОВАНИЕ: Поиск/Фильтрация ---
            action_logger.info(
                f"Пользователь '{
                    request.user.username}' выполнил поиск по запросу: '{search_query_param}'. ")

        if year:
            try:
                year_int = int(year)
                queryset = queryset.filter(issue_date__year=year_int)
            except (ValueError, TypeError):
                action_logger.warning(
                    f"Неверный формат года '{year}' в фильтре от пользователя '{
                        request.user.username}'.")
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

        if doc_type:
            queryset = queryset.filter(doc_type=doc_type)

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
            years = Order.objects.dates('issue_date', 'year', order='ASC')
            years_list = [(year.year, year.year) for year in years]

            cache.set(years_cache_key, years_list, timeout=3600)

        return years_list

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else 'Anonymous'
        queryset = self.get_filtered_queryset(self.request)
        action_logger.info(
            f"ПРОСМОТР: Пользователь '{user}' просмотрел реестр. Параметры фильтрации: {
                self.request.GET.urlencode()}")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Приказы'
        context["search"] = self.request.GET.get("search", "")
        context["filter_doc_num"] = self.request.GET.get("filter_doc_num", "")
        context["selected_year"] = self.request.GET.get(
            "filter_year", date.today().year)
        context["selected_doc_type"] = self.request.GET.get(
            "filter_doc_type", "")
        context["years"] = self.get_year_choices()
        context['order_form'] = OrderForm()
        context['login_form'] = AuthenticationForm()
        context['export_field_map'] = EXPORT_FIELD_MAP
        context['organization_name'] = settings.ORGANIZATION_NAME

        return context


class OrderDetailView(DetailView):
    model = Order
    template_name = 'orders/includes/inc__modal_order_detail.html'
    context_object_name = 'order'

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()

            # --- ЛОГИРОВАНИЕ: Просмотр деталей ---
            action_logger.info(
                f"ПРОСМОТР: Пользователь '{
                    request.user.username}' просмотрел приказ " f"ID: {
                    self.object.pk}, Номер: {
                    self.object.document_number}.")
            context = self.get_context_data(object=self.object)
            return self.render_to_response(context)
        except Order.DoesNotExist:
            # --- ЛОГИРОВАНИЕ: Провал просмотра (объект не найден) ---
            action_logger.warning(
                f"ПРОВАЛ: Попытка просмотра несуществующего приказа с PK={
                    kwargs.get('pk')} " f"пользователем '{
                    request.user.username}'.")
            return HttpResponse('Приказ не найден.', status=404)
        except Exception as e:
            # --- ЛОГИРОВАНИЕ: Критическая ошибка сервера ---
            error_logger.error(
                f"КРИТИЧЕСКАЯ ОШИБКА: при просмотре деталей приказа PK={
                    kwargs.get('pk')} " f"пользователем '{
                    request.user.username}': {e}", exc_info=True)
            return HttpResponse('Внутренняя ошибка сервера.', status=500)


class AddOrderView(SuccessMessageMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'orders/add_order.html'
    success_url = reverse_lazy('orders:index')

    def get(self, request, *args, **kwargs):
        # --- ЛОГИРОВАНИЕ: Открытие формы создания ---
        action_logger.info(
            f"ОТКРЫТИЕ: Пользователь '{
                request.user.username}' открыл форму для СОЗДАНИЯ приказа.")
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            form.instance.author = self.request.user
            response = super().form_valid(form)

            # --- ЛОГИРОВАНИЕ: Успешное создание ---
            action_logger.info(
                f"УСПЕХ: Приказ №{
                    self.object.document_number} (ID: {
                    self.object.pk}) " f"успешно создан пользователем '{
                    self.request.user.username}'.")

            if self.request.headers.get(
                    'x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            else:
                return response
        except IntegrityError as e:
            # --- ЛОГИРОВАНИЕ: Ошибка целостности БД (например, дубликат номера) ---
            error_logger.warning(
                f"ПРОВАЛ (DB): Пользователь '{self.request.user.username}' "
                f"пытался создать приказ с ошибкой целостности данных: {e}"
            )
            # Передаем ошибку в форму, чтобы показать пользователю
            form.add_error(
                None, "Ошибка сохранения: возможно, приказ с таким номером уже существует.")
            return self.form_invalid(form)
        except Exception as e:
            # --- ЛОГИРОВАНИЕ: Критическая ошибка сервера ---
            error_logger.error(
                f"КРИТИЧЕСКАЯ ОШИБКА: при создании приказа пользователем '{
                    self.request.user.username}': {e}", exc_info=True)
            # Передаем общую ошибку
            form.add_error(
                None, "Произошла внутренняя ошибка сервера при сохранении.")
            return self.form_invalid(form)

    def form_invalid(self, form):
        errors = form.errors.as_data()
        action_logger.warning(
            f"ПРОВАЛ (Валидация): Пользователь '{self.request.user.username}' "
            f"не смог создать приказ. Ошибки: {errors}"
        )
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(
                {'success': False, 'errors': form.errors}, status=400)
        else:
            return super().form_invalid(form)


class OrderEditView(UpdateView):
    model = Order
    template_name = 'orders/includes/inc__modal_edit_order.html'
    form_class = OrderForm
    context_object_name = 'order'

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()

            # --- ЛОГИРОВАНИЕ: Открытие формы редактирования ---
            action_logger.info(
                f"ОТКРЫТИЕ: Пользователь '{
                    request.user.username}' открыл форму для РЕДАКТИРОВАНИЯ приказа ID: {
                    self.object.pk}.")

            form = self.get_form()
            return render(
                request,
                self.template_name,
                self.get_context_data(
                    form=form))
        except Order.DoesNotExist:
            action_logger.warning(
                f"ПРОВАЛ: Попытка открыть редактирование несуществующего приказа с PK={
                    kwargs.get('pk')} " f"пользователем '{
                    request.user.username}'.")
            return HttpResponse('Приказ не найден.', status=404)

    def form_valid(self, form):
        try:
            submitted_data = form.cleaned_data
            form.save()
            # --- ЛОГИРОВАНИЕ: Успешное обновление ---
            action_logger.info(
                f"УСПЕХ: Приказ №{
                    self.object.document_number} (ID: {
                    self.object.pk}) "
                f"успешно ОБНОВЛЕН пользователем '{
                    self.request.user.username}'. "
                # ДОБАВЛЕНО: запись данных формы
                f"Измененные данные: {submitted_data}"
            )
            # Предполагаем, что это AJAX-ответ после успешного сохранения
            return render(self.request, 'orders/empty.html')
        except IntegrityError as e:
            error_logger.warning(
                f"ПРОВАЛ (DB): Пользователь '{
                    self.request.user.username}' " f"пытался обновить приказ (ID: {
                    self.object.pk}) с ошибкой целостности: {e}")
            form.add_error(
                None, "Ошибка обновления: возможно, приказ с таким номером уже существует.")
            return self.form_invalid(form)
        except Exception as e:
            error_logger.error(
                f"КРИТИЧЕСКАЯ ОШИБКА: при обновлении приказа ID={
                    self.object.pk} " f"пользователем '{
                    self.request.user.username}': {e}",
                exc_info=True)
            form.add_error(
                None, "Произошла внутренняя ошибка сервера при сохранении.")
            return self.form_invalid(form)

    def form_invalid(self, form):
        # --- ЛОГИРОВАНИЕ: Ошибка валидации ---
        errors = form.errors.as_data()
        action_logger.warning(
            f"ПРОВАЛ (Валидация): Пользователь '{
                self.request.user.username}' " f"не смог обновить приказ (ID: {
                self.object.pk if hasattr(
                    self, 'object') and self.object else 'N/A'}). Ошибки: {errors}")
        return render(
            self.request,
            self.template_name,
            self.get_context_data(
                form=form))


class DeleteOrderView(DeleteView):
    model = Order
    template_name = 'orders/includes/inc__modal_delete_order.html'
    success_url = reverse_lazy('orders:index')
    success_message = 'Приказ успешно удален.'

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()

            # --- ЛОГИРОВАНИЕ: Открытие формы удаления ---
            action_logger.info(
                f"ОТКРЫТИЕ: Пользователь '{
                    request.user.username}' открыл подтверждение УДАЛЕНИЯ приказа ID: {
                    self.object.pk}.")

            context = self.get_context_data(object=self.object)
            return render(request, self.template_name, context)
        except Order.DoesNotExist:
            action_logger.warning(
                f"ПРОВАЛ: Попытка открыть форму удаления несуществующего приказа с PK={
                    kwargs.get('pk')} " f"пользователем '{
                    request.user.username}'.")
            return HttpResponse('Приказ не найден.', status=404)

    def post(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            document_number = self.object.document_number
            pk_to_delete = self.object.pk
            success_url = self.get_success_url()
            self.object.delete()

            # --- ЛОГИРОВАНИЕ: Успешное удаление ---
            action_logger.info(
                f"УСПЕХ: Пользователь '{request.user.username}' подтвердил и выполнил УДАЛЕНИЕ "
                f"приказа №{document_number} (ID: {pk_to_delete})."
            )

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'success': True, 'redirect_url': success_url})
            else:
                return HttpResponseRedirect(success_url)
        except Order.DoesNotExist:
            # --- ЛОГИРОВАНИЕ: Провал удаления (объект не найден) ---
            action_logger.warning(
                f"ПРОВАЛ: Попытка POST-удаления несуществующего приказа с PK={kwargs.get('pk')} "
                f"пользователем '{request.user.username}'."
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'success': False, 'error': 'Приказ не найден.'}, status=404)
            else:
                return HttpResponse('Приказ не найден.', status=404)
        except Exception as e:
            # --- ЛОГИРОВАНИЕ: Критическая ошибка сервера ---
            error_logger.error(
                f"КРИТИЧЕСКАЯ ОШИБКА: при удалении приказа PK={
                    kwargs.get('pk')} " f"пользователем '{
                    request.user.username}': {e}",
                exc_info=True)
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'success': False, 'error': 'Ошибка сервера.'}, status=500)
            else:
                return HttpResponse('Внутренняя ошибка сервера.', status=500)


class ExportToExcelView(OrderQuerysetMixin, View):
    DOC_TYPE_CHOICES = dict(Order.DOC_TYPE_CHOICES)

    def get(self, request, *args, **kwargs):
        selected_fields = request.GET.getlist('fields')
        # --- ЛОГИРОВАНИЕ: Инициализация экспорта ---
        action_logger.info(
            f"ЭКСПОРТ: Пользователь '{
                request.user.username}' инициировал экспорт. Выбраны поля: {
                ', '.join(selected_fields)}.")
        if not selected_fields:
            # --- ЛОГИРОВАНИЕ: Провал экспорта (нет полей) ---
            action_logger.warning(
                f"ПРОВАЛ: Экспорт отменен. Пользователь '{
                    request.user.username}' " f"не выбрал ни одного поля для экспорта.")
            return HttpResponse(
                "Ошибка: не выбрано ни одного поля для экспорта.",
                status=400)

        try:
            queryset = self.get_filtered_queryset(request)

            headers = []
            valid_field_names = []

            for field_name, field_label in EXPORT_FIELD_MAP.items():
                if field_name in selected_fields:
                    headers.append(field_label)
                    valid_field_names.append(field_name)

            orders_data = queryset.values_list(*valid_field_names)

            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.append(headers)

            doc_type_index = None
            try:
                doc_type_index = valid_field_names.index('doc_type')
            except ValueError:
                pass

            for order_tuple in orders_data:
                row = list(order_tuple)

                for i, value in enumerate(row):
                    if isinstance(value, date):
                        row[i] = value.strftime('%d.%m.%Y')
                    elif i == doc_type_index and value:
                        row[i] = self.DOC_TYPE_CHOICES.get(value, value)
                    elif value is None:
                        row[i] = ''

                sheet.append(row)

            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=orders_export.xlsx'
            workbook.save(response)

            # --- ЛОГИРОВАНИЕ: Успешный экспорт ---
            action_logger.info(
                f"УСПЕХ: Пользователь '{request.user.username}' "
                f"успешно экспортировал {len(orders_data)} приказов."
            )

            return response

        except Exception as e:
            # --- ЛОГИРОВАНИЕ: Критическая ошибка экспорта ---
            error_logger.error(
                f"КРИТИЧЕСКАЯ ОШИБКА: при экспорте приказов "
                f"пользователем '{request.user.username}': {e}",
                exc_info=True
            )
            return HttpResponse(
                "Внутренняя ошибка сервера при экспорте.",
                status=500)
