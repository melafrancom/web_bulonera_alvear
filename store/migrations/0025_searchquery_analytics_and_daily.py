# Generated manually for SearchQuery analytics extension and SearchQueryDaily model.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0024_populate_normalized_relation_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='searchquery',
            options={
                'ordering': ['-search_count', '-last_searched_at'],
                'verbose_name': 'Consulta de Búsqueda',
                'verbose_name_plural': 'Consultas de Búsqueda (Analytics)',
            },
        ),
        migrations.AddField(
            model_name='searchquery',
            name='last_results_count',
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.AddField(
            model_name='searchquery',
            name='matched_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='searchquery',
            name='unmatched_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='searchquery',
            name='last_searched_at',
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
        migrations.CreateModel(
            name='SearchQueryDaily',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True)),
                ('matched_count', models.PositiveIntegerField(default=0)),
                ('unmatched_count', models.PositiveIntegerField(default=0)),
                ('last_results_count', models.PositiveIntegerField(default=0)),
                (
                    'search_query',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='daily_stats',
                        to='store.searchquery',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Métrica Diaria de Búsqueda',
                'verbose_name_plural': 'Métricas Diarias de Búsqueda',
                'ordering': ['-date'],
            },
        ),
        migrations.AddIndex(
            model_name='searchquerydaily',
            index=models.Index(fields=['date', 'search_query'], name='idx_sqdaily_date_query'),
        ),
        migrations.AddConstraint(
            model_name='searchquerydaily',
            constraint=models.UniqueConstraint(
                fields=('search_query', 'date'),
                name='unique_search_query_daily_date',
            ),
        ),
    ]
