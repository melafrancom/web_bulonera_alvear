"""
Servicio centralizado de consulta y formateo de Horarios Comerciales.
Fuente única de verdad para templates, Schema.org y vistas.
"""
from datetime import timedelta
import json
import logging
from django.core.cache import cache
from django.utils import timezone

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


def _format_time_short(t) -> str:
    """
    Formato corto sin cero a la izquierda en la hora: 8:00, 18:30.
    # POR QUÉ: Evita dependencia de glibc '%-H' para compatibilidad total con Windows y Linux.
    """
    if not t:
        return ''
    return f"{t.hour}:{t.minute:02d}"


def _format_time_24h(t) -> str:
    """
    Formato estándar ISO 24h con cero inicial: 08:00, 18:30.
    """
    if not t:
        return ''
    return f"{t.hour:02d}:{t.minute:02d}"


def _format_day_range_label(start_day: int, end_day: int, separator: str = "–") -> str:
    """
    Devuelve la etiqueta legible del rango de días (ej. 'Lun–Vie', 'Lun - Vie', 'Sáb').
    """
    if start_day == end_day:
        return DAYS_NAMES_ES[start_day]
    return f"{DAYS_NAMES_ES[start_day]}{separator}{DAYS_NAMES_ES[end_day]}"


def _group_contiguous_days(periods_by_day: dict) -> list[tuple[int, int, list]]:
    """
    Agrupa días consecutivos (1..7) que posean exactamente los mismos períodos de atención.
    # POR QUÉ: Permite representar dinámicamente cualquier esquema comercial (ej. Lun–Vie,
    # Lun–Jue + Vie, o Lun–Sáb) sin perder turnos ni asumir esquemas rígidos.
    # REGLA: Solo agrupa días abiertos con intervalos idénticos en secuencia contigua.
    """
    groups = []
    current_start = None
    current_end = None
    current_intervals = None
    current_periods = None

    for d in range(1, 8):
        plist = periods_by_day.get(d, [])
        intervals = tuple((p.opening_time, p.closing_time) for p in plist) if plist else None

        if intervals is None:
            if current_start is not None:
                groups.append((current_start, current_end, current_periods))
                current_start = None
                current_end = None
                current_intervals = None
                current_periods = None
        else:
            if current_start is not None and intervals == current_intervals and d == current_end + 1:
                current_end = d
            else:
                if current_start is not None:
                    groups.append((current_start, current_end, current_periods))
                current_start = d
                current_end = d
                current_intervals = intervals
                current_periods = plist

    if current_start is not None:
        groups.append((current_start, current_end, current_periods))

    return groups


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
        'special_schema_specifications': [],
        'special_schema_specifications_json': json.dumps([]),
        'today_exception': None,
        'evaluated_date': '',
    }


def get_business_hours_data() -> dict:
    """
    Obtiene los horarios comerciales activos desde caché o base de datos.
    # QUÉ: Retorna diccionario estructurado con formatos corto, multilínea, Schema.org y feriado de hoy.
    # POR QUÉ: Fuente única de verdad centralizada para navbar, footer, checkout, contacto y SEO.
    # REGLA: Valida que la fecha evaluada corresponda a la fecha local de hoy (America/Argentina/Buenos_Aires).
    # Si cambió la medianoche, reevalúa automáticamente las excepciones del día.
    """
    cache_key = 'business_hours_active'
    cached = cache.get(cache_key)
    today = timezone.localdate()
    today_iso = today.isoformat()

    if cached and isinstance(cached, dict):
        if cached.get('evaluated_date') == today_iso:
            return cached

    try:
        from web_bulonera.models import BusinessHoursSetting
        setting = BusinessHoursSetting.objects.prefetch_related('periods', 'exceptions').first()
        if not setting:
            data = get_default_business_hours()
            data['evaluated_date'] = today_iso
            cache.set(cache_key, data, timeout=3600)
            return data

        periods = list(setting.periods.all())
        if not periods:
            data = get_default_business_hours()
            data['holiday_note'] = setting.holiday_note or 'Domingos y feriados cerrado'
            data['evaluated_date'] = today_iso
            cache.set(cache_key, data, timeout=3600)
            return data

        # 1. Agrupar períodos por día (1..7)
        periods_by_day = {}
        for p in periods:
            periods_by_day.setdefault(p.day, []).append(p)

        # 2. Schema.org specifications agrupadas por horario
        specs_by_hours = {}
        for p in periods:
            hours_key = (_format_time_24h(p.opening_time), _format_time_24h(p.closing_time))
            day_en = DAYS_MAP.get(p.day, 'Monday')
            specs_by_hours.setdefault(hours_key, []).append(day_en)

        schema_specs = []
        for (op, cl), days in specs_by_hours.items():
            schema_specs.append({
                '@type': 'OpeningHoursSpecification',
                'dayOfWeek': days,
                'opens': op,
                'closes': cl,
            })

        # 3. Agrupación dinámica de días consecutivos para presentación
        groups = _group_contiguous_days(periods_by_day)

        # 4. Construir líneas visibles estructuradas (para footer, contacto, history)
        lines = []
        for start_day, end_day, g_periods in groups:
            shift_strs = [f"{_format_time_24h(p.opening_time)} - {_format_time_24h(p.closing_time)}" for p in g_periods]
            corrido = ""
            if len(g_periods) == 1:
                p0 = g_periods[0]
                dur = (p0.closing_time.hour + p0.closing_time.minute / 60.0) - (p0.opening_time.hour + p0.opening_time.minute / 60.0)
                if dur >= 8.0:
                    corrido = " (Corrido)"
            hours_str = f"{' y '.join(shift_strs)}{corrido}"
            label = _format_day_range_label(start_day, end_day, separator=" - ")
            lines.append({'label': label, 'hours': hours_str})

        # Evaluar estado de domingo y feriados para lines
        is_sunday_open = any(start_day <= 7 <= end_day for start_day, end_day, _ in groups)
        raw_note = (setting.holiday_note or '').strip()
        is_default_closed_note = raw_note.lower() in ('', 'domingos y feriados cerrado', 'cerrado')

        if not is_sunday_open:
            dom_hours = 'Cerrado' if is_default_closed_note else raw_note
            lines.append({'label': 'Dom y Feriados', 'hours': dom_hours})
        else:
            fer_hours = 'Cerrado' if is_default_closed_note else raw_note
            lines.append({'label': 'Feriados', 'hours': fer_hours})

        # 5. Resumen corto (para topbar / navbar / checkout / nosotros)
        short_parts = []
        for start_day, end_day, g_periods in groups:
            shift_strs = [f"{_format_time_short(p.opening_time)}–{_format_time_short(p.closing_time)}" for p in g_periods]
            combined_shifts = " y ".join(shift_strs)
            group_label = _format_day_range_label(start_day, end_day, separator="–")
            short_parts.append(f"{group_label} {combined_shifts}")

        short_summary = " · ".join(short_parts) if short_parts else "Lun–Vie 8:00–20:00 · Sáb 8:00–13:00 y 16:00–18:30"

        # 6. Excepciones / Feriados (Opción A: Google specialOpeningHours + alerta del día)
        today_exc = next((e for e in setting.exceptions.all() if e.date == today), None)
        today_exception_data = None
        if today_exc:
            reason_str = today_exc.reason.strip() if today_exc.reason else "Feriado"
            if today_exc.is_closed:
                hours_display = "Cerrado"
                badge_text = f"Hoy feriado ({reason_str}): Cerrado"
            else:
                op_special = _format_time_24h(today_exc.opening_time)
                cl_special = _format_time_24h(today_exc.closing_time)
                hours_display = f"{op_special} - {cl_special}"
                badge_text = f"Hoy horario especial ({reason_str}): {op_special} a {cl_special}"

            today_exception_data = {
                'date': today_iso,
                'is_closed': today_exc.is_closed,
                'hours': hours_display,
                'reason': reason_str,
                'badge_text': badge_text,
            }

        special_schema_specs = []
        horizon = today + timedelta(days=90)
        for exc in setting.exceptions.all():
            if today <= exc.date <= horizon:
                date_str = exc.date.isoformat()
                if exc.is_closed:
                    special_schema_specs.append({
                        '@type': 'OpeningHoursSpecification',
                        'validFrom': date_str,
                        'validThrough': date_str,
                        'opens': '00:00',
                        'closes': '00:00',
                    })
                elif exc.opening_time and exc.closing_time:
                    special_schema_specs.append({
                        '@type': 'OpeningHoursSpecification',
                        'validFrom': date_str,
                        'validThrough': date_str,
                        'opens': _format_time_24h(exc.opening_time),
                        'closes': _format_time_24h(exc.closing_time),
                    })

        data = {
            'short': short_summary,
            'holiday_note': setting.holiday_note or 'Domingos y feriados cerrado',
            'lines': lines,
            'schema_specifications': schema_specs,
            'schema_specifications_json': json.dumps(schema_specs),
            'special_schema_specifications': special_schema_specs,
            'special_schema_specifications_json': json.dumps(special_schema_specs),
            'today_exception': today_exception_data,
            'evaluated_date': today_iso,
        }
        cache.set(cache_key, data, timeout=3600)
        return data

    except Exception as exc:
        logger.warning("Error consultando BusinessHoursSetting: %s", exc)
        return get_default_business_hours()
