# Generated by Django 5.0.6 on 2025-05-04 02:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0002_product_gtin_product_meta_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='productgallery',
            name='alt',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
