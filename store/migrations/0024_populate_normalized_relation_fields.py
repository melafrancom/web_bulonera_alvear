# Generated manually for data backfill of normalized technical relation fields.

from django.db import migrations

from store.relation_utils import normalize_thread_format, parse_diameter_and_pitch


def populate_normalized_fields(apps, schema_editor):
    """
    Backfill en lotes con bulk_update sin invocar Product.save().

    POR QUÉ: Product.save() concatena dimensiones en name, puede regenerar slugs
    y encola tareas de imagen; usar bulk_update preserva el catálogo intacto.
    """
    Product = apps.get_model('store', 'Product')
    batch = []
    queryset = Product.objects.only(
        'id',
        'diameter',
        'thread_formats',
        'diameter_nominal',
        'thread_pitch',
        'thread_normalized',
    ).iterator(chunk_size=1000)

    for product in queryset:
        diam_nom, diam_pitch = parse_diameter_and_pitch(product.diameter)
        thread_fam, thread_pitch_from_fmt = normalize_thread_format(product.thread_formats)
        new_pitch = diam_pitch or thread_pitch_from_fmt

        if (
            product.diameter_nominal != diam_nom
            or product.thread_pitch != new_pitch
            or product.thread_normalized != thread_fam
        ):
            product.diameter_nominal = diam_nom
            product.thread_pitch = new_pitch
            product.thread_normalized = thread_fam
            batch.append(product)

        if len(batch) >= 1000:
            Product.objects.bulk_update(
                batch,
                ['diameter_nominal', 'thread_pitch', 'thread_normalized'],
                batch_size=1000,
            )
            batch.clear()

    if batch:
        Product.objects.bulk_update(
            batch,
            ['diameter_nominal', 'thread_pitch', 'thread_normalized'],
            batch_size=1000,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0023_product_related_subcategories_and_relation_fields'),
    ]

    operations = [
        migrations.RunPython(populate_normalized_fields, migrations.RunPython.noop),
    ]
