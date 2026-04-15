from django.db import models
from django.core.cache import cache

class SiteTheme(models.Model):
    """
    Configuración visual del sitio. Modelo Singleton (solo debe existir UNA instancia).
    Cambiable desde Django Admin sin re-deploy.
    """
    name = models.CharField(max_length=50, default="Default")

    # Color Primario (botones, navbar, links)
    primary_50  = models.CharField(max_length=7, default='#EFF6FF')
    primary_100 = models.CharField(max_length=7, default='#DBEAFE')
    primary_200 = models.CharField(max_length=7, default='#BFDBFE')
    primary_300 = models.CharField(max_length=7, default='#93C5FD')
    primary_400 = models.CharField(max_length=7, default='#60A5FA')
    primary_500 = models.CharField(max_length=7, default='#3B82F6')
    primary_600 = models.CharField(max_length=7, default='#2563EB')  # ← botones
    primary_700 = models.CharField(max_length=7, default='#1D4ED8')  # ← hover
    primary_800 = models.CharField(max_length=7, default='#1E40AF')  # ← DEFAULT
    primary_900 = models.CharField(max_length=7, default='#1E3A8A')  # ← navbar

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
    subbar_from    = models.CharField(max_length=7, default='#1D4ED8', verbose_name="Barra de Título — Color inicial")
    subbar_to      = models.CharField(max_length=7, default='#1E3A8A', verbose_name="Barra de Título — Color final")
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
            return
        super().save(*args, **kwargs)
        # Invalidar caché al guardar
        cache.delete('site_theme_active')
