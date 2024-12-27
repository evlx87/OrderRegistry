import datetime
import io

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook

from orders.forms import OrderForm
from orders.models import Order


# Create your views here.
class IndexView(ListView):
    model = Order
    template_name = 'orders/index.html'
    context_object_name = 'orders'

    def get_year_choices(self):
        years = Order.objects.dates('issue_date', 'year', order='ASC')
        return [(year.year, year.year) for year in years]

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get("search")
        filter_doc_num = self.request.GET.get("filter_doc_num")
        filter_year = self.request.GET.get("filter_year")

        if search:
            queryset = queryset.filter(document_title__icontains=search)
        if filter_doc_num:
            queryset = queryset.filter(document_number__exact=filter_doc_num)
        if filter_year:
            queryset = queryset.filter(issue_date__year=int(filter_year))

        queryset = queryset.order_by('-issue_date')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Приказы'
        context["search"] = self.request.GET.get("search", "")
        context["filter_doc_num"] = self.request.GET.get("filter_doc_num", "")
        context["years"] = self.get_year_choices()
        context["selected_year"] = self.request.GET.get("filter_year", datetime.date.today().year)
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
        orders = Order.objects.all().order_by('-id')  # Получение всех объектов модели заказа

        # Данные для заполнения таблицы
        data = [['Номер документа', 'Дата издания', 'Название документа', 'Кем подписан документ',
                 'Ответственный исполнитель', 'Кому передан (ответственный за исполнение приказа)',
                 'Кому передано на хранение', 'Номер гербового бланка', 'Примечание']]

        for order in orders:
            data.append([
                order.document_number,
                order.issue_date.strftime('%d.%m.%Y'),
                order.document_title,
                order.signed_by,
                order.responsible_executor,
                order.transferred_to_execution,
                order.transferred_for_storage,
                order.heraldic_blank_number,
                order.note
            ])

        # Создание новой рабочей книги
        wb = Workbook()
        ws = wb.active

        # Заполнение данными
        for row in data:
            ws.append(row)

        # Установка ширины колонок
        dim_holder = {}
        for col in range(len(data[0])):
            for row in range(1, len(data) + 1):
                column_letter = get_column_letter(col + 1)
                cell_value = str(ws.cell(row=row, column=col + 1).value)
                try:
                    dim_holder[column_letter].append(len(cell_value))
                except KeyError:
                    dim_holder[column_letter] = [len(cell_value)]

        for col, widths in dim_holder.items():
            max_width = max(widths)
            ws.column_dimensions[col].width = max_width + 3

        # Сохранение файла в память
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # Отправка файла пользователю
        response = HttpResponse(
            content=output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="orders_{datetime.datetime.now().strftime("%Y-%m-%d")}.xlsx"'
        return response
