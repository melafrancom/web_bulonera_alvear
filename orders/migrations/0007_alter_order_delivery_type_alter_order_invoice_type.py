from django.db import migrations, models
from django.utils import timezone


def migrate_historical_orders(apps, schema_editor):
    """
    Clasifica todas las órdenes existentes creadas bajo el flujo anterior
    sin selección explícita del usuario como 'unspecified'.
    # REGLA: Irreversible por diseño (reverse_code=None).
    """
    Order = apps.get_model('orders', 'Order')
    cutoff_date = timezone.now()
    Order.objects.filter(created_at__lte=cutoff_date).update(
        delivery_type='unspecified',
        invoice_type='unspecified'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_order_business_name_order_delivery_type_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='delivery_type',
            field=models.CharField(choices=[('pickup', 'Retiro en Local (Av. Alvear 1301)'), ('shipping', 'Envío a convenir (Interior / NEA)'), ('unspecified', 'No especificado (Histórico)')], default='unspecified', max_length=20, verbose_name='Modalidad de Entrega'),
        ),
        migrations.AlterField(
            model_name='order',
            name='invoice_type',
            field=models.CharField(choices=[('B', 'Consumidor Final (Factura B)'), ('A', 'Responsable Inscripto (Factura A)'), ('unspecified', 'No especificado (Histórico)')], default='unspecified', max_length=15, verbose_name='Tipo de Factura'),
        ),
        migrations.RunPython(
            migrate_historical_orders,
            reverse_code=None,
            elidable=False,
        ),
    ]

