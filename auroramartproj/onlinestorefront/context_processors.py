from adminpanel.models import Product
from .models import Cart


def categories_processor(request):
    """Provide categories and their subcategories for the header dropdown.

    Returns a list of dicts: { 'name': category_name, 'subcategories': [sub1, sub2, ...] }
    """
    # Collect distinct category names
    category_names = (
        Product.objects.exclude(product_category__isnull=True)
        .exclude(product_category="")
        .values_list("product_category", flat=True)
        .distinct()
    )
    categories = []
    for cname in category_names:
        subs_qs = (
            Product.objects.filter(product_category=cname)
            .exclude(product_subcategory__isnull=True)
            .exclude(product_subcategory="")
            .values_list("product_subcategory", flat=True)
            .distinct()
        )
        # sort subcategories alphabetically (case-insensitive)
        sub_list = sorted(list(subs_qs), key=lambda s: (s or '').lower())
        categories.append({"name": cname, "subcategories": sub_list})

    # sort categories alphabetically (case-insensitive)
    categories = sorted(categories, key=lambda c: (c.get('name') or '').lower())

    return {"site_categories": categories}


def cart_count_processor(request):
    """Expose cart_item_count for header badge. Safe if no cart or anon."""
    count = 0
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        try:
            cart = Cart.objects.get(user=user)
            count = cart.items.count()
        except Cart.DoesNotExist:
            count = 0
    return {"cart_item_count": count}
