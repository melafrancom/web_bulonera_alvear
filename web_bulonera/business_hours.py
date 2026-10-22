"""
Servicio centralizado de consulta y formateo de Horarios Comerciales.
Fuente única de verdad para templates, Schema.org y vistas.
"""
import json
import logging
from django.core.cache import cache

logger = logging.getLogger('django')

DAYS_MAP = {
    1: 'Monday',
    2: 'Tuesday',
    3: 'Wednesday',
    4: 'Thursday',
    5: 'Friday',
    6: 'Saturday',
    7: 'Sunday',
}

DAYS_NAMES_ES = {
    1: 'Lun',
    2: 'Mar',
    3: 'Mié',
    4: 'Jue',
    5: 'Vie',
    6: 'Sáb',
    7: 'Dom',
}


def get_default_business_hours() -> dict:
    """Devuelve la configuración predeterminada de horarios cuando aún no hay datos en la BD."""
    specs = [
        {
            '@type': 'OpeningHoursSpecification',
            'dayOfWeek': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            'opens': '08:00',
            'closes': '20:00',
        },
        {
            '@type': 'OpeningHoursSpecification',
            'dayOfWeek': ['Saturday'],
            'opens': '08:00',
            'closes': '13:00',
        },
        {
            '@type': 'OpeningHoursSpecification',
            'dayOfWeek': ['Saturday'],
            'opens': '16:00',
            'closes': '18:30',
        },
    ]
    return {
        'short': 'Lun–Vie 8:00–20:00 · Sáb 8:00–13:00 y 16:00–18:30',
        'holiday_note': 'Domingos y feriados cerrado',
        'lines': [
            {'label': 'Lun - Vie', 'hours': '08:00 - 20:00 (Corrido)'},
            {'label': 'Sáb', 'hours': '08:00 - 13:00 y 16:00 - 18:30'},
            {'label': 'Dom y Feriados', 'hours': 'Cerrado'},
        ],
        'schema_specifications': specs,
        'schema_specifications_json': json.dumps(specs),
    }


def get_business_hours_data() -> dict:
    """
    Obtiene los horarios comerciales activos desde caché o base de datos.
    Invalida y reconstruye la presentación para templates y Schema.org.
    """
    cache_key = 'business_hours_active'
    cached = cache.get(cache_key)
    if cached and isinstance(cached, dict):
        return cached

    try:
        from web_bulonera.models import BusinessHoursSetting
        setting = BusinessHoursSetting.objects.prefetch_related('periods', 'exceptions').first()
        if not setting:
            data = get_default_business_hours()
            cache.set(cache_key, data, timeout=3600)
            return data

        periods = list(setting.periods.all())
        if not periods:
            data = get_default_business_hours()
            data['holiday_note'] = setting.holiday_note or 'Domingos y feriados cerrado'
            cache.set(cache_key, data, timeout=3600)
            return data

        # Agrupar períodos por día
        periods_by_day = {}
        for p in periods:
            periods_by_day.setdefault(p.day, []).append(p)

        # Construir Schema.org specifications
        schema_specs = []
        for p in periods:
            day_en = DAYS_MAP.get(p.day, 'Monday')
            schema_specs.append({
                '@type': 'OpeningHoursSpecification',
                'dayOfWeek': [day_en],
                'opens': p.opening_time.strftime('%H:%M'),
                'closes': p.closing_time.strftime('%H:%M'),
            })

        # Construir líneas visibles estructuradas
        lines = []
        # Detectar si Lun a Vie son idénticos
        weekday_periods = [periods_by_day.get(d, []) for d in range(1, 6)]
        same_weekdays = True
        first_wd_strs = [f"{p.opening_time.strftime('%H:%M')} - {p.closing_time.strftime('%H:%M')}" for p in weekday_periods[0]]
        for wd_p in weekday_periods[1:]:
            curr_strs = [f"{p.opening_time.strftime('%H:%M')} - {p.closing_time.strftime('%H:%M')}" for p in wd_p]
            if curr_strs != first_wd_strs:
                same_weekdays = False
                break

        if same_weekdays and first_wd_strs:
            corrido = "(Corrido)" if len(first_wd_strs) == 1 else ""
            lines.append({
                'label': 'Lun - Vie',
                'hours': f"{' y '.join(first_wd_strs)} {corrido}".strip()
            })
        else:
            for d in range(1, 6):
                d_p = periods_by_day.get(d, [])
                if d_p:
                    hours_str = " y ".join(f"{p.opening_time.strftime('%H:%M')} - {p.closing_time.strftime('%H:%M')}" for p in d_p)
                    lines.append({'label': DAYS_NAMES_ES[d], 'hours': hours_str})

        # Sábado
        sat_periods = periods_by_day.get(6, [])
        if sat_periods:
            sat_strs = [f"{p.opening_time.strftime('%H:%M')} - {p.closing_time.strftime('%H:%M')}" for p in sat_periods]
            lines.append({'label': 'Sáb', 'hours': ' y '.join(sat_strs)})
        else:
            lines.append({'label': 'Sáb', 'hours': 'Cerrado'})

        # Domingos y feriados
        sun_periods = periods_by_day.get(7, [])
        if sun_periods:
            sun_strs = [f"{p.opening_time.strftime('%H:%M')} - {p.closing_time.strftime('%H:%M')}" for p in sun_periods]
            lines.append({'label': 'Dom', 'hours': ' y '.join(sun_strs)})
        else:
            lines.append({'label': 'Dom y Feriados', 'hours': setting.holiday_note or 'Cerrado'})

        # Resumen corto (para topbar / navbar)
        short_parts = []
        if same_weekdays and first_wd_strs:
            short_parts.append(f"Lun–Vie {first_wd_strs[0].replace(':00', ':00').replace(' - ', '–')}")
        if sat_periods:
            sat_short = ' y '.join(f"{p.opening_time.strftime('%-H:%M' if hasattr(p.opening_time, 'strftime') else '%H:%M')}–{p.closing_time.strftime('%-H:%M' if hasattr(p.closing_time, 'strftime') else '%H:%M')}" for p in sat_periods)
            short_parts.append(f"Sáb {sat_short}")
        short_summary = " · ".join(short_parts) if short_parts else "Lun–Vie 8:00–20:00 · Sáb 8:00–13:00 y 16:00–18:30"

        data = {
            'short': short_summary,
            'holiday_note': setting.holiday_note or 'Domingos y feriados cerrado',
            'lines': lines,
            'schema_specifications': schema_specs,
            'schema_specifications_json': json.dumps(schema_specs),
        }
        cache.set(cache_key, data, timeout=3600)
        return data

    except Exception as exc:
        logger.warning("Error consultando BusinessHoursSetting: %s", exc)
        return get_default_business_hours()
