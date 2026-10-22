"""
Tests unitarios para la centralización de Horarios Comerciales (Fase 2).
Valida singleton, cálculo de intervalos semanales, Schema.org y caché.
"""
import pytest
from datetime import time, date
from django.core.cache import cache
from django.core.exceptions import ValidationError
from web_bulonera.models import BusinessHoursSetting, BusinessHoursPeriod, BusinessHoursException
from web_bulonera.business_hours import get_business_hours_data, get_default_business_hours


@pytest.mark.django_db
class TestBusinessHoursModel:
    """Tests para los modelos de horarios comerciales."""

    def test_singleton_business_hours_setting(self):
        """No permite crear más de una instancia de BusinessHoursSetting."""
        BusinessHoursSetting.objects.all().delete()
        s1 = BusinessHoursSetting.objects.create(name="Horario 1")
        assert BusinessHoursSetting.objects.count() == 1

        # Intento de crear segunda instancia
        s2 = BusinessHoursSetting(name="Horario 2")
        s2.save()
        # El conteo debe seguir siendo 1
        assert BusinessHoursSetting.objects.count() == 1

    def test_period_validation_opening_before_closing(self):
        """clean() rechaza períodos con opening_time >= closing_time."""
        setting = BusinessHoursSetting.objects.first()
        if not setting:
            setting = BusinessHoursSetting.objects.create(name="Horario Test")

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
        assert len(defaults['lines']) >= 2

    def test_get_business_hours_data_caching_and_invalidation(self):
        """Verifica que se cachee el resultado y se invalide al guardar."""
        cache.clear()
        setting, _ = BusinessHoursSetting.objects.get_or_create(name="Horario Test")
        BusinessHoursPeriod.objects.get_or_create(
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

    def test_schema_org_json_serialization(self):
        """Verifica que schema_specifications_json sea JSON válido y parseable."""
        import json
        data = get_business_hours_data()
        specs = json.loads(data['schema_specifications_json'])
        assert isinstance(specs, list)
        for spec in specs:
            assert spec['@type'] == 'OpeningHoursSpecification'
            assert 'opens' in spec
            assert 'closes' in spec
            assert 'dayOfWeek' in spec


@pytest.mark.django_db
class TestBusinessHoursContextProcessor:
    """Verifica la disponibilidad global de business_hours en peticiones web."""

    def test_business_hours_in_template_context(self, client):
        """El context processor inyecta business_hours en todas las vistas."""
        response = client.get('/')
        assert response.status_code == 200
        assert 'business_hours' in response.context
        bh = response.context['business_hours']
        assert 'short' in bh
        assert 'lines' in bh
        assert 'schema_specifications_json' in bh
