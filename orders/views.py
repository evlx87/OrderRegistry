from datetime import date

import openpyxl
from django.conf import settings
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
        return self.get_filtered_queryset(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Приказы'
        context["search"] = self.request.GET.get("search", "")
        context["filter_doc_num"] = self.request.GET.get("filter_doc_num", "")
        context["selected_year"] = self.request.GET.get("filter_year", date.today().year)
        context["selected_doc_type"] = self.request.GET.get("filter_doc_type", "")
        context["years"] = self.get_year_choices()
        context['order_form'] = OrderForm()
        context['login_form'] = AuthenticationForm()
        context['export_field_map'] = EXPORT_FIELD_MAP
        context['organization_name'] = settings.ORGANIZATION_NAME

        return context


class AddOrderView(SuccessMessageMixin, CreateView):
    model = Order
    form_class = OrderForm
    template_name = 'orders/add_order.html'
    success_url = reverse_lazy('orders:index')

    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)

        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        else:
            return response

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(
                {'success': False, 'errors': form.errors}, status=400)
        else:
            return super().form_invalid(form)


class OrderDetailView(DetailView):
    model = Order
    template_name = 'orders/includes/inc__modal_order_detail.html'
    context_object_name = 'order'


class OrderEditView(UpdateView):
    model = Order
    template_name = 'orders/includes/inc__modal_edit_order.html'
    form_class = OrderForm
    context_object_name = 'order'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return render(
            request,
            self.template_name,
            self.get_context_data(
                form=form))

    def form_valid(self, form):
        form.save()
        return render(self.request, 'orders/empty.html')

    def form_invalid(self, form):
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
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'redirect_url': success_url})
        else:
            return HttpResponseRedirect(success_url)


class ExportToExcelView(OrderQuerysetMixin, View):
    DOC_TYPE_CHOICES = dict(Order.DOC_TYPE_CHOICES)

    def get(self, request, *args, **kwargs):
        selected_fields = request.GET.getlist('fields')

        if not selected_fields:
            return HttpResponse(
                "Ошибка: не выбрано ни одного поля для экспорта.",
                status=400)

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

        return response
