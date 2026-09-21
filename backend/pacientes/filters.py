"""Preserve CI ordering without sorting randomized ciphertext."""
from django.db.models import Case, When, Value, IntegerField
from rest_framework.filters import OrderingFilter


class PatientOrderingFilter(OrderingFilter):
    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset
        if any(item.lstrip('-') == 'ci' for item in ordering):
            rows = list(queryset.values_list('pk', 'ci'))
            values = sorted(set(ci for _, ci in rows))
            ranks = {ci: rank for rank, ci in enumerate(values)}
            clauses = [When(pk=pk, then=Value(ranks[ci])) for pk, ci in rows]
            queryset = queryset.annotate(_ci_order=Case(*clauses, default=Value(0), output_field=IntegerField()))
            ordering = [item.replace('ci', '_ci_order') if item.lstrip('-') == 'ci' else item for item in ordering]
        return queryset.order_by(*ordering)
