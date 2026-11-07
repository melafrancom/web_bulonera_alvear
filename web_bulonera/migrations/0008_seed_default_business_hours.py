# Generated data migration for default business hours seeding

from datetime import time
from django.db import migrations


def seed_business_hours(apps, schema_editor):
    """
    Siembra la configuración y períodos predeterminados de horarios comerciales.
    # POR QUÉ: Evita que el sitio quede con horarios vacíos o cerrados si el administrador
    # edita por primera vez desde Django Admin agregando solo un período parcial.
    # REGLA: Idempotente: solo crea si no existe ninguna configuración o períodos.
    """
    BusinessHoursSetting = apps.get_model('web_bulonera', 'BusinessHoursSetting')
    BusinessHoursPeriod = apps.get_model('web_bulonera', 'BusinessHoursPeriod')

    setting = BusinessHoursSetting.objects.first()
    if not setting:
        setting = BusinessHoursSetting.objects.create(
            name="Horario Comercial Principal",
            holiday_note="Domingos y feriados cerrado",
        )

    # Si ya tiene períodos configurados manualmente en producción, no alterar nada
    if BusinessHoursPeriod.objects.filter(setting=setting).exists():
        return

    # Lunes a Viernes: 08:00 - 20:00 (turnos corridos)
    for day in range(1, 6):
        BusinessHoursPeriod.objects.create(
            setting=setting,
            day=day,
            opening_time=time(8, 0),
            closing_time=time(20, 0),
        )

    # Sábado: 08:00 - 13:00 y 16:00 - 18:30 (turnos partidos)
    BusinessHoursPeriod.objects.create(
        setting=setting,
        day=6,
        opening_time=time(8, 0),
        closing_time=time(13, 0),
    )
    BusinessHoursPeriod.objects.create(
        setting=setting,
        day=6,
        opening_time=time(16, 0),
        closing_time=time(18, 30),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('web_bulonera', '0007_businesshourssetting_businesshoursperiod_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_business_hours, reverse_code=migrations.RunPython.noop),
    ]

