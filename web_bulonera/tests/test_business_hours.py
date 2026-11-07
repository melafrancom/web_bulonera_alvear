"""
Tests exhaustivos para la centralización dinámica de Horarios Comerciales.
Valida singleton, cálculo de intervalos semanales, turnos partidos, días asimétricos,
excepciones/feriados (Opción A), validación de formsets en Admin y renderizado dinámico en vistas.
"""
from datetime import time, timedelta
import json
import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.forms.models import inlineformset_factory
from django.utils import timezone

from web_bulonera.models import BusinessHoursSetting, BusinessHoursPeriod, BusinessHoursException
from web_bulonera.business_hours import get_business_hours_data, get_default_business_hours
from web_bulonera.admin import (
    BusinessHoursPeriodInlineFormSet,
    BusinessHoursExceptionInlineFormSet,
)


@pytest.mark.django_db
class TestBusinessHoursModel:
    """Tests para los modelos de horarios comerciales."""

    def test_singleton_business_hours_setting(self):
        """No permite crear más de una instancia de BusinessHoursSetting."""
        BusinessHoursSetting.objects.all().delete()
        s1 = BusinessHoursSetting.objects.create(name="Horario 1")
        assert BusinessHoursSetting.objects.count() == 1

        s2 = BusinessHoursSetting(name="Horario 2")
        s2.save()
        assert BusinessHoursSetting.objects.count() == 1

    def test_singleton_load_method(self):
        """load() recupera la instancia existente o crea una inicial idempotente."""
        BusinessHoursSetting.objects.all().delete()
        assert BusinessHoursSetting.objects.count() == 0

        inst1 = BusinessHoursSetting.load()
        assert inst1.pk is not None
        assert BusinessHoursSetting.objects.count() == 1

        inst2 = BusinessHoursSetting.load()
        assert inst2.pk == inst1.pk
        assert BusinessHoursSetting.objects.count() == 1

    def test_period_validation_opening_before_closing(self):
        """clean() rechaza períodos con opening_time >= closing_time."""
        setting = BusinessHoursSetting.load()

        period_inverted = BusinessHoursPeriod(
            setting=setting,
            day=1,
            opening_time=time(20, 0),
            closing_time=time(8, 0)
        )
        with pytest.raises(ValidationError):
            period_inverted.clean()

        period_equal = BusinessHoursPeriod(
            setting=setting,
            day=1,
            opening_time=time(12, 0),
            closing_time=time(12, 0)
        )
        with pytest.raises(ValidationError):
            period_equal.clean()

    def test_exception_validation(self):
        """clean() en BusinessHoursException valida coherencia entre cerrado y horas especiales."""
        setting = BusinessHoursSetting.load()
        today = timezone.localdate()

        # Si no está cerrado, debe tener horas de apertura y cierre
        exc_invalid = BusinessHoursException(
            setting=setting,
            date=today,
            is_closed=False,
            opening_time=None,
            closing_time=None,
        )
        with pytest.raises(ValidationError):
            exc_invalid.clean()

        # Si las horas están invertidas, rechaza
        exc_inverted = BusinessHoursException(
            setting=setting,
            date=today,
            is_closed=False,
            opening_time=time(18, 0),
            closing_time=time(9, 0),
        )
        with pytest.raises(ValidationError):
            exc_inverted.clean()


@pytest.mark.django_db
class TestBusinessHoursAdminFormsets:
    """Tests para la validación estricta de solapamientos y reglas en Django Admin."""

    def test_period_formset_detects_overlap(self):
        """El formset rechaza turnos que se superponen en el mismo día."""
        setting = BusinessHoursSetting.load()
        PeriodFormSet = inlineformset_factory(
            BusinessHoursSetting,
            BusinessHoursPeriod,
            formset=BusinessHoursPeriodInlineFormSet,
            fields=('day', 'opening_time', 'closing_time'),
            extra=2,
        )
        data = {
            'periods-TOTAL_FORMS': '2',
            'periods-INITIAL_FORMS': '0',
            'periods-MIN_NUM_FORMS': '0',
            'periods-MAX_NUM_FORMS': '1000',
            # Turno 1: 08:00 a 14:00
            'periods-0-day': '1',
            'periods-0-opening_time': '08:00',
            'periods-0-closing_time': '14:00',
            # Turno 2: 13:00 a 18:00 (solapa de 13:00 a 14:00)
            'periods-1-day': '1',
            'periods-1-opening_time': '13:00',
            'periods-1-closing_time': '18:00',
        }
        formset = PeriodFormSet(data, instance=setting, prefix='periods')
        assert not formset.is_valid()
        assert any("Solapamiento horario en Lunes" in str(err) for err in formset.non_form_errors())

    def test_period_formset_requires_at_least_one_period(self):
        """El formset impide eliminar todos los períodos activos."""
        setting = BusinessHoursSetting.load()
        PeriodFormSet = inlineformset_factory(
            BusinessHoursSetting,
            BusinessHoursPeriod,
            formset=BusinessHoursPeriodInlineFormSet,
            fields=('day', 'opening_time', 'closing_time'),
            extra=1,
        )
        data = {
            'periods-TOTAL_FORMS': '1',
            'periods-INITIAL_FORMS': '0',
            'periods-MIN_NUM_FORMS': '0',
            'periods-MAX_NUM_FORMS': '1000',
        }
        formset = PeriodFormSet(data, instance=setting, prefix='periods')
        assert not formset.is_valid()
        assert any("Debe configurar al menos un período" in str(err) for err in formset.non_form_errors())

    def test_exception_formset_conflicting_closed_and_hours(self):
        """El formset rechaza marcar cerrado y tener otra fila con horario en la misma fecha."""
        setting = BusinessHoursSetting.load()
        today = timezone.localdate().strftime('%Y-%m-%d')
        ExceptionFormSet = inlineformset_factory(
            BusinessHoursSetting,
            BusinessHoursException,
            formset=BusinessHoursExceptionInlineFormSet,
            fields=('date', 'reason', 'is_closed', 'opening_time', 'closing_time'),
            extra=2,
        )
        data = {
            'exceptions-TOTAL_FORMS': '2',
            'exceptions-INITIAL_FORMS': '0',
            'exceptions-MIN_NUM_FORMS': '0',
            'exceptions-MAX_NUM_FORMS': '1000',
            # Fila 1: Cerrado
            'exceptions-0-date': today,
            'exceptions-0-is_closed': 'on',
            'exceptions-0-reason': 'Feriado',
            # Fila 2: Abierto
            'exceptions-1-date': today,
            'exceptions-1-is_closed': '',
            'exceptions-1-opening_time': '09:00',
            'exceptions-1-closing_time': '13:00',
            'exceptions-1-reason': 'Turno especial',
        }
        formset = ExceptionFormSet(data, instance=setting, prefix='exceptions')
        assert not formset.is_valid()
        assert any("Conflicto en la fecha" in str(err) for err in formset.non_form_errors())


@pytest.mark.django_db
class TestBusinessHoursService:
    """Tests para el servicio get_business_hours_data."""

    def test_default_business_hours_structure(self):
        """Verifica la estructura y contenido predeterminado."""
        defaults = get_default_business_hours()
        assert 'short' in defaults
        assert 'lines' in defaults
        assert 'schema_specifications' in defaults
        assert 'schema_specifications_json' in defaults
        assert 'special_schema_specifications' in defaults
        assert len(defaults['lines']) >= 2

    def test_get_business_hours_data_caching_and_invalidation(self):
        """Verifica que se cachee el resultado y se invalide al guardar."""
        cache.clear()
        setting = BusinessHoursSetting.load()
        BusinessHoursPeriod.objects.filter(setting=setting).delete()
        BusinessHoursPeriod.objects.create(
            setting=setting, day=1, opening_time=time(8, 0), closing_time=time(20, 0)
        )
        cache.clear()
        data1 = get_business_hours_data()
        assert cache.get('business_hours_active') is not None

        # Guardar setting invalida la caché
        setting.holiday_note = "Cerrado por inventario"
        setting.save()
        assert cache.get('business_hours_active') is None

        data2 = get_business_hours_data()
        assert data2['holiday_note'] == "Cerrado por inventario"
        assert cache.get('business_hours_active') is not None

    def test_split_shift_on_weekdays(self):
        """
        # REGLA: Si lunes a viernes tiene turno partido, short y lines deben
        # mostrar AMBOS turnos (ej. 8:00–12:30 y 16:00–20:00), sin truncar el segundo.
        """
        cache.clear()
        setting = BusinessHoursSetting.load()
        BusinessHoursPeriod.objects.filter(setting=setting).delete()

        # Lun a Vie turno partido
        for d in range(1, 6):
            BusinessHoursPeriod.objects.create(setting=setting, day=d, opening_time=time(8, 0), closing_time=time(12, 30))
            BusinessHoursPeriod.objects.create(setting=setting, day=d, opening_time=time(16, 0), closing_time=time(20, 0))

        # Sábado turno simple
        BusinessHoursPeriod.objects.create(setting=setting, day=6, opening_time=time(8, 0), closing_time=time(13, 0))

        data = get_business_hours_data()
        assert "Lun–Vie 8:00–12:30 y 16:00–20:00" in data['short']
        assert "Sáb 8:00–13:00" in data['short']

        # En lines debe verse estructurado
        lun_vie_line = next(line for line in data['lines'] if line['label'] == 'Lun - Vie')
        assert "08:00 - 12:30 y 16:00 - 20:00" in lun_vie_line['hours']
        assert "(Corrido)" not in lun_vie_line['hours']

    def test_asymmetric_weekdays_and_open_sunday(self):
        """Días hábiles con horarios dispares y domingos abiertos se agrupan limpiamente."""
        cache.clear()
        setting = BusinessHoursSetting.load()
        BusinessHoursPeriod.objects.filter(setting=setting).delete()

        # Lun a Jue (1..4): 08:00 a 18:00
        for d in range(1, 5):
            BusinessHoursPeriod.objects.create(setting=setting, day=d, opening_time=time(8, 0), closing_time=time(18, 0))

        # Vie (5): 08:00 a 16:00
        BusinessHoursPeriod.objects.create(setting=setting, day=5, opening_time=time(8, 0), closing_time=time(16, 0))

        # Dom (7): 09:00 a 13:00
        BusinessHoursPeriod.objects.create(setting=setting, day=7, opening_time=time(9, 0), closing_time=time(13, 0))

        data = get_business_hours_data()
        assert "Lun–Jue 8:00–18:00" in data['short']
        assert "Vie 8:00–16:00" in data['short']
        assert "Dom 9:00–13:00" in data['short']

    def test_today_exception_closed_and_special_hours(self):
        """
        # REGLA: Opción A: si hoy es fecha de excepción, expone today_exception y
        # puebla special_schema_specifications para Schema.org.
        """
        cache.clear()
        setting = BusinessHoursSetting.load()
        BusinessHoursPeriod.objects.filter(setting=setting).delete()
        BusinessHoursException.objects.filter(setting=setting).delete()

        # Semanal básico
        for d in range(1, 6):
            BusinessHoursPeriod.objects.create(setting=setting, day=d, opening_time=time(8, 0), closing_time=time(20, 0))

        today = timezone.localdate()
        # Excepción 1: Hoy cerrado por feriado
        BusinessHoursException.objects.create(
            setting=setting,
            date=today,
            is_closed=True,
            reason="Día de la Bandera"
        )
        # Excepción 2: En 5 días horario especial
        future_date = today + timedelta(days=5)
        BusinessHoursException.objects.create(
            setting=setting,
            date=future_date,
            is_closed=False,
            opening_time=time(9, 0),
            closing_time=time(13, 0),
            reason="Inventario"
        )

        data = get_business_hours_data()
        assert data['today_exception'] is not None
        assert data['today_exception']['is_closed'] is True
        assert "Hoy feriado (Día de la Bandera): Cerrado" == data['today_exception']['badge_text']

        # Verificar specialOpeningHoursSpecification en Schema.org
        special_specs = json.loads(data['special_schema_specifications_json'])
        assert len(special_specs) == 2
        today_spec = next(s for s in special_specs if s['validFrom'] == today.isoformat())
        assert today_spec['opens'] == '00:00'
        assert today_spec['closes'] == '00:00'

        future_spec = next(s for s in special_specs if s['validFrom'] == future_date.isoformat())
        assert future_spec['opens'] == '09:00'
        assert future_spec['closes'] == '13:00'

    def test_midnight_cache_auto_refresh(self):
        """
        # REGLA: Si la fecha local evaluada en la caché difiere de hoy (pasó la medianoche),
        # get_business_hours_data recalcula automáticamente.
        """
        cache.clear()
        setting = BusinessHoursSetting.load()
        yesterday_iso = (timezone.localdate() - timedelta(days=1)).isoformat()

        fake_cached_data = {
            'short': 'Horario de ayer',
            'evaluated_date': yesterday_iso,
        }
        cache.set('business_hours_active', fake_cached_data, timeout=3600)

        # La consulta detecta cambio de fecha y recalcula
        data = get_business_hours_data()
        assert data['short'] != 'Horario de ayer'
        assert data['evaluated_date'] == timezone.localdate().isoformat()


@pytest.mark.django_db
class TestBusinessHoursViewsIntegration:
    """Verifica que todas las vistas públicas reflejen los cambios sin cadenas hardcodeadas."""

    def test_business_hours_in_template_context(self, client):
        """El context processor inyecta business_hours en todas las vistas."""
        response = client.get('/')
        assert response.status_code == 200
        assert 'business_hours' in response.context
        bh = response.context['business_hours']
        assert 'short' in bh
        assert 'lines' in bh
        assert 'schema_specifications_json' in bh

    def test_views_reflect_custom_admin_schedule(self, client):
        """
        Al cambiar los horarios en BD, /nosotros/, /history/, /contact/ y /llms.txt
        muestran los nuevos valores y ninguna cadena obsoleta previa.
        """
        cache.clear()
        setting = BusinessHoursSetting.load()
        BusinessHoursPeriod.objects.filter(setting=setting).delete()
        BusinessHoursException.objects.filter(setting=setting).delete()

        # Configuramos un horario personalizado reconocible: 07:30 a 19:30 Lun-Vie
        for d in range(1, 6):
            BusinessHoursPeriod.objects.create(setting=setting, day=d, opening_time=time(7, 30), closing_time=time(19, 30))
        # Sábados: 09:00 a 14:00
        BusinessHoursPeriod.objects.create(setting=setting, day=6, opening_time=time(9, 0), closing_time=time(14, 0))

        setting.save()
        cache.delete('business_hours_active')

        # 1. /nosotros/
        resp_nosotros = client.get('/nosotros/')
        assert resp_nosotros.status_code == 200
        content_nosotros = resp_nosotros.content.decode('utf-8')
        assert "7:30–19:30" in content_nosotros
        assert "9:00–14:00" in content_nosotros
        # Asegurar ausencia de las viejas cadenas estáticas
        assert "8–20hs y sábados 8–13hs" not in content_nosotros
        assert "Lun–Vie 8:00–20:00 · Sáb 8:00–13:00" not in content_nosotros

        # 2. /history/
        resp_history = client.get('/history/')
        assert resp_history.status_code == 200
        content_history = resp_history.content.decode('utf-8')
        assert "07:30 - 19:30" in content_history
        assert "09:00 - 14:00" in content_history
        assert "Lun–Vie 8:00–20:00<br>Sáb 8:00–13:00" not in content_history

        # 3. /contact/
        resp_contact = client.get('/contact/')
        assert resp_contact.status_code == 200
        content_contact = resp_contact.content.decode('utf-8')
        assert "07:30 - 19:30" in content_contact
        assert "09:00 - 14:00" in content_contact

        # 4. /llms.txt
        resp_llms = client.get('/llms.txt')
        assert resp_llms.status_code == 200
        content_llms = resp_llms.content.decode('utf-8')
        assert "7:30–19:30" in content_llms
        assert "9:00–14:00" in content_llms
