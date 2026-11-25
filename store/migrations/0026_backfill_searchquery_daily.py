# Generated manually for data backfill of historical SearchQuery records into SearchQueryDaily.

from django.db import migrations
from django.db.models import F
from django.utils import timezone


def backfill_search_queries(apps, schema_editor):
    """
    Migra registros históricos de demanda oculta sin pérdida de métricas.

    POR QUÉ: Los registros previos de SearchQuery solo medían búsquedas sin resultados
    en search_count. Se replica ese volumen en unmatched_count y en SearchQueryDaily
    para que los filtros de período (90 días / histórico) reflejen la historia previa.
    """
    SearchQuery = apps.get_model('store', 'SearchQuery')
    SearchQueryDaily = apps.get_model('store', 'SearchQueryDaily')

    SearchQuery.objects.filter(matched_count=0, unmatched_count=0).update(
        unmatched_count=F('search_count'),
        last_results_count=0,
    )

    existing_daily_ids = set(
        SearchQueryDaily.objects.values_list('search_query_id', flat=True).distinct()
    )

    batch = []
    queryset = SearchQuery.objects.only(
        'id',
        'search_count',
        'matched_count',
        'unmatched_count',
        'last_results_count',
        'last_searched_at',
    ).iterator(chunk_size=1000)

    for sq in queryset:
        if sq.id in existing_daily_ids:
            continue

        if sq.last_searched_at is None:
            record_date = timezone.localdate()
        elif timezone.is_aware(sq.last_searched_at):
            record_date = timezone.localdate(sq.last_searched_at)
        else:
            record_date = sq.last_searched_at.date()

        batch.append(
            SearchQueryDaily(
                search_query_id=sq.id,
                date=record_date,
                matched_count=sq.matched_count,
                unmatched_count=sq.unmatched_count,
                last_results_count=sq.last_results_count,
            )
        )

        if len(batch) >= 1000:
            SearchQueryDaily.objects.bulk_create(batch, batch_size=1000, ignore_conflicts=True)
            batch.clear()

    if batch:
        SearchQueryDaily.objects.bulk_create(batch, batch_size=1000, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0025_searchquery_analytics_and_daily'),
    ]

    operations = [
        migrations.RunPython(backfill_search_queries, migrations.RunPython.noop),
    ]
