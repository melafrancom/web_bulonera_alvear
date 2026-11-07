from django.db import models
from django.core.cache import cache
import logging

logger = logging.getLogger('django')

class SiteTheme(models.Model):
    """
    Configuración visual del sitio. Modelo Singleton (solo debe existir UNA instancia).
    Cambiable desde Django Admin sin re-deploy.
    """
    name = models.CharField(max_length=50, default="Default")

    # Color Primario (botones, navbar, links)
    primary_50  = models.CharField(max_length=7, default='#E2ECF6')  # Gris Nieve Azulado
    primary_100 = models.CharField(max_length=7, default='#C5D9ED')
    primary_200 = models.CharField(max_length=7, default='#9AC1F0')  # Celeste Pastel
    primary_300 = models.CharField(max_length=7, default='#7BAEE0')
    primary_400 = models.CharField(max_length=7, default='#5B95D0')
    primary_500 = models.CharField(max_length=7, default='#4A6FA5')  # Acero Claro
    primary_600 = models.CharField(max_length=7, default='#3A5F8F')
    primary_700 = models.CharField(max_length=7, default='#2A4F79')
    primary_800 = models.CharField(max_length=7, default='#1B3A5C')  # Azul Marino BA (DEFAULT)
    primary_900 = models.CharField(max_length=7, default='#122840')

    # Color Acento (estrellas, badges de oferta)
    accent_400  = models.CharField(max_length=7, default='#FBBF24')
    accent_500  = models.CharField(max_length=7, default='#F59E0B')  # ← DEFAULT
    accent_600  = models.CharField(max_length=7, default='#D97706')

    # Fondo global (modo claro) - Gris muy suave tipo Apple
    soft_bg     = models.CharField(max_length=7, default='#F5F5F7', verbose_name="Fondo global (modo claro)")

    # ---------- NAVBAR / HEADER ----------
    navbar_bg      = models.CharField(max_length=7, default='#FFFFFF', verbose_name="Navbar — Fondo")
    navbar_text    = models.CharField(max_length=7, default='#0F172A', verbose_name="Navbar — Texto e íconos")
    navbar_opacity = models.PositiveSmallIntegerField(default=100, verbose_name="Navbar — Opacidad (%)", help_text="0 (transparente) a 100 (sólido)")

    # ---------- TOPBAR ----------
    topbar_text    = models.CharField(max_length=7, default='#475569', verbose_name="Topbar — Texto")

    # ---------- SUBTITLE BAR ----------
    subbar_from    = models.CharField(max_length=7, default='#1B3A5C', verbose_name="Barra de Título — Color inicial")
    subbar_to      = models.CharField(max_length=7, default='#122840', verbose_name="Barra de Título — Color final")
    subbar_opacity = models.PositiveSmallIntegerField(default=100, verbose_name="Barra de Título — Opacidad (%)")

    # ---------- FOOTER ----------
    footer_bg      = models.CharField(max_length=7, default='#0F172A', verbose_name="Footer — Fondo")
    footer_text    = models.CharField(max_length=7, default='#CBD5E1', verbose_name="Footer — Texto")
    footer_opacity = models.PositiveSmallIntegerField(default=100, verbose_name="Footer — Opacidad (%)")

    # ---------- HOME SECTIONS ----------
    quickcat_bg      = models.CharField(max_length=7, default='#F5F5F7', verbose_name="Categorías Rápidas — Fondo")
    quickcat_opacity = models.PositiveSmallIntegerField(default=100, verbose_name="Categorías Rápidas — Opacidad (%)")
    
    bestseller_bg      = models.CharField(max_length=7, default='#FFFFFF', verbose_name="Lo más vendido — Fondo")
    bestseller_opacity = models.PositiveSmallIntegerField(default=100, verbose_name="Lo más vendido — Opacidad (%)")

    # Métodos de utilidad para colores RGBA
    def _hex_to_rgb(self, hex_val):
        try:
            hex_val = hex_val.lstrip('#')
            return ",".join(str(int(hex_val[i:i+2], 16)) for i in (0, 2, 4))
        except:
            return "255,255,255"

    @property
    def navbar_bg_rgb(self): return self._hex_to_rgb(self.navbar_bg)
    
    @property
    def subbar_from_rgb(self): return self._hex_to_rgb(self.subbar_from)
    
    @property
    def subbar_to_rgb(self): return self._hex_to_rgb(self.subbar_to)
    
    @property
    def footer_bg_rgb(self): return self._hex_to_rgb(self.footer_bg)
    
    @property
    def quickcat_bg_rgb(self): return self._hex_to_rgb(self.quickcat_bg)
    
    @property
    def bestseller_bg_rgb(self): return self._hex_to_rgb(self.bestseller_bg)

    @property
    def navbar_opacity_dec(self): return f"{self.navbar_opacity / 100.0:.2f}"
    
    @property
    def subbar_opacity_dec(self): return f"{self.subbar_opacity / 100.0:.2f}"
    
    @property
    def footer_opacity_dec(self): return f"{self.footer_opacity / 100.0:.2f}"
    
    @property
    def quickcat_opacity_dec(self): return f"{self.quickcat_opacity / 100.0:.2f}"
    
    @property
    def bestseller_opacity_dec(self): return f"{self.bestseller_opacity / 100.0:.2f}"

    class Meta:
        verbose_name = "Tema del Sitio"
        verbose_name_plural = "Tema del Sitio"

    def __str__(self):
        return f"Tema: {self.name}"

    def save(self, *args, **kwargs):
        # Asegurar que sea singleton
        if not self.pk and SiteTheme.objects.exists():
            logger.warning(
                "Intento bloqueado de crear segunda instancia de SiteTheme. "
                "Use SiteTheme.objects.first() para editar el tema existente."
            )
            return
        super().save(*args, **kwargs)
        # Invalidar caché al guardar
        cache.delete('site_theme_active')


class BusinessHoursSetting(models.Model):
    """
    Configuración centralizada de horarios comerciales (Singleton).
    Fuente única de verdad editable desde Django Admin sin necesidad de redeploy.
    """
    name = models.CharField(max_length=100, default="Horario Comercial Principal")
    holiday_note = models.CharField(
        max_length=200,
        blank=True,
        default="Domingos y feriados cerrado",
        verbose_name="Aviso de Feriados y Domingos"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Horario Comercial"
        verbose_name_plural = "Horario Comercial"

    def __str__(self):
        return self.name

    @classmethod
    def load(cls):
        """
        Obtiene la única instancia de configuración de horarios o crea una inicial.
        # REGLA: Patrón Singleton para configuración global editable desde Admin.
        """
        instance = cls.objects.first()
        if not instance:
            instance = cls.objects.create(name="Horario Comercial Principal")
        return instance

    def save(self, *args, **kwargs):
        if not self.pk and BusinessHoursSetting.objects.exists():
            logger.warning("Intento bloqueado de crear segunda instancia de BusinessHoursSetting.")
            return
        super().save(*args, **kwargs)
        cache.delete('business_hours_active')


class BusinessHoursPeriod(models.Model):
    """
    Intervalo semanal de atención para un día de la semana.
    Permite turnos corridos o turnos partidos (ej. sábado 08:00–13:00 y 16:00–18:30).
    """
    DAYS_OF_WEEK = (
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
        (6, 'Sábado'),
        (7, 'Domingo'),
    )

    setting = models.ForeignKey(
        BusinessHoursSetting,
        on_delete=models.CASCADE,
        related_name='periods'
    )
    day = models.PositiveSmallIntegerField(
        choices=DAYS_OF_WEEK,
        verbose_name="Día de la semana"
    )
    opening_time = models.TimeField(verbose_name="Hora de apertura")
    closing_time = models.TimeField(verbose_name="Hora de cierre")

    class Meta:
        verbose_name = "Período de Atención"
        verbose_name_plural = "Períodos de Atención"
        ordering = ['day', 'opening_time']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.opening_time and self.closing_time:
            if self.opening_time >= self.closing_time:
                raise ValidationError("La hora de apertura debe ser anterior a la hora de cierre.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        cache.delete('business_hours_active')

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete('business_hours_active')

    def __str__(self):
        return f"{self.get_day_display()}: {self.opening_time.strftime('%H:%M')} - {self.closing_time.strftime('%H:%M')}"


class BusinessHoursException(models.Model):
    """
    Excepción puntual de horario por feriado o fecha especial.
    """
    setting = models.ForeignKey(
        BusinessHoursSetting,
        on_delete=models.CASCADE,
        related_name='exceptions'
    )
    date = models.DateField(verbose_name="Fecha")
    is_closed = models.BooleanField(
        default=True,
        verbose_name="Cerrado todo el día"
    )
    opening_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Hora de apertura especial"
    )
    closing_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Hora de cierre especial"
    )
    reason = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Motivo (ej. Feriado Nacional, Inventario)"
    )

    class Meta:
        verbose_name = "Excepción / Feriado"
        verbose_name_plural = "Excepciones / Feriados"
        ordering = ['date']

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.is_closed:
            if not self.opening_time or not self.closing_time:
                raise ValidationError("Si el local no está cerrado, debe indicar hora de apertura y cierre especial.")
            if self.opening_time >= self.closing_time:
                raise ValidationError("La hora de apertura especial debe ser anterior a la de cierre.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        cache.delete('business_hours_active')

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete('business_hours_active')

    def __str__(self):
        estado = "Cerrado" if self.is_closed else f"{self.opening_time.strftime('%H:%M')}-{self.closing_time.strftime('%H:%M')}"
        return f"{self.date.strftime('%d/%m/%Y')} ({estado}) - {self.reason or 'Sin motivo'}"

