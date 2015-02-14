from django.db.models import Count
from django.views.generic import TemplateView
from pretixpresale.views import EventViewMixin, CartDisplayMixin


class EventIndex(EventViewMixin, CartDisplayMixin, TemplateView):
    template_name = "pretixpresale/event/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch all items
        items = self.request.event.items.all().select_related(
            'category',  # for re-grouping
        ).prefetch_related(
            'properties',  # for .get_all_available_variations()
            'quotas', 'variations__quotas'  # for .availability()
        ).annotate(quotac=Count('quotas')).filter(
            quotac__gt=0
        ).order_by('category__position', 'category_id', 'name')

        for item in items:
            item.available_variations = sorted(item.get_all_available_variations(),
                                               key=lambda vd: vd.ordered_values())
            item.has_variations = (len(item.available_variations) != 1
                                   or not item.available_variations[0].empty())
            if not item.has_variations:
                item.cached_availability = list(item.check_quotas())
                item.cached_availability[1] = min(item.cached_availability[1],
                                                  self.request.event.max_items_per_order)
                item.price = item.available_variations[0]['price']
            else:
                for var in item.available_variations:
                    var.cached_availability = list(var['variation'].check_quotas())
                    var.cached_availability[1] = min(var.cached_availability[1],
                                                     self.request.event.max_items_per_order)

        # Regroup those by category
        context['items_by_category'] = sorted([
            # a group is a tuple of a category and a list of items
            (cat, [i for i in items if i.category_id == cat.identity])
            for cat in set([i.category for i in items])  # insert categories into a set for uniqueness
        ], key=lambda group: (group[0].position, group[0].pk))  # a set is unsorted, so sort again by category

        context['cart'] = self.get_cart()
        return context