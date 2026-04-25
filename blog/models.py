"""Blog Models - Posts, Social Metadata, and Tags"""
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone


class PostTag(models.Model):
    """Tag/Category for organizing blog posts"""
    name = models.CharField(max_length=50, unique=True, help_text="Nombre del tag")
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Post(models.Model):
    """Blog post - puede ser artículo original o repost de red social"""
    
    POST_TYPE_CHOICES = [
        ('article', 'Artículo Original'),
        ('social_repost', 'Repost de Red Social'),
    ]
    
    # Contenido
    title = models.CharField(
        max_length=200,
        unique=True,
        help_text="Título del artículo"
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        blank=True,
        help_text="URL amigable (auto-generado desde el título)"
    )
    content = models.TextField(
        help_text="Contenido del artículo (HTML permitido)"
    )
    excerpt = models.CharField(
        max_length=300,
        blank=True,
        help_text="Resumen corto para previews y meta description"
    )
    post_type = models.CharField(
        max_length=20,
        choices=POST_TYPE_CHOICES,
        default='article',
        help_text="Tipo de post"
    )
    
    # Media (FK a media_bank centralizado)
    featured_image = models.ForeignKey(
        'media_bank.ImageAsset',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='blog_posts',
        help_text="Imagen destacada (desde Banco de Imágenes)"
    )
    image_alt = models.CharField(
        max_length=255,
        blank=True,
        help_text="Texto alternativo de la imagen"
    )
    
    # SEO (patrón heredado de store.Product)
    meta_title = models.CharField(
        max_length=70,
        blank=True,
        help_text="Meta título para SEO (máx 70 caracteres)"
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        help_text="Meta descripción para SEO (máx 160 caracteres)"
    )
    meta_keywords = models.CharField(
        max_length=255,
        blank=True,
        help_text="Palabras clave separadas por comas"
    )
    
    # Taxonomía
    tags = models.ManyToManyField(
        PostTag,
        blank=True,
        related_name='posts',
        help_text="Tags para categorizar el post"
    )
    
    # Auditoría y publicación
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='blog_posts',
        help_text="Autor del post (admin)"
    )
    created_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha de creación"
    )
    modified_date = models.DateTimeField(
        auto_now=True,
        help_text="Última modificación"
    )
    published_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de publicación"
    )
    is_published = models.BooleanField(
        default=False,
        help_text="¿Está publicado?"
    )
    
    # Métricas
    views_count = models.PositiveIntegerField(
        default=0,
        help_text="Número de vistas"
    )
    
    class Meta:
        ordering = ['-published_date']
        verbose_name = "Artículo de Blog"
        verbose_name_plural = "Artículos de Blog"
        indexes = [
            models.Index(fields=['is_published', '-published_date']),
            models.Index(fields=['slug']),
            models.Index(fields=['post_type']),
        ]
    
    def clean(self):
        """
        Validación de consistencia de negocio.
        Ejecutado por Django Admin antes de save().
        
        Raises:
            ValidationError: Si un social_repost se publica sin SocialMetadata.
        """
        from django.core.exceptions import ValidationError
        
        # Regla: social_repost publicado REQUIERE SocialMetadata
        if self.post_type == 'social_repost' and self.is_published:
            has_metadata = (
                hasattr(self, 'social_metadata') and 
                self.social_metadata is not None
            )
            if not has_metadata:
                raise ValidationError({
                    'post_type': (
                        "Un post de tipo 'Repost de Red Social' no puede publicarse "
                        "sin completar la sección 'Social Media Post' (plataforma + URL)."
                    )
                })
    
    def save(self, *args, **kwargs):
        """Auto-generar slug y rellenar SEO por defecto"""
        if not self.slug:
            self.slug = self._generate_unique_slug()
        
        # Auto-rellenar meta_title si está vacío
        if not self.meta_title:
            self.meta_title = self.title[:70]
        
        # Auto-rellenar meta_description desde excerpt
        if not self.meta_description and self.excerpt:
            self.meta_description = self.excerpt[:160]
        
        # Auto-setear published_date cuando se publica
        if self.is_published and not self.published_date:
            self.published_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    def _generate_unique_slug(self):
        """
        Genera slug único basado en título (Smart Slug Regeneration).
        Si el título contiene solo caracteres especiales, usa fallback dinámico con timestamp.
        """
        import time
        
        base_slug = slugify(self.title)
        if not base_slug:
            # Fallback dinámico: 'post' + timestamp para garantizar unicidad
            base_slug = f"post-{int(time.time())}"
        
        slug = base_slug
        counter = 1
        
        # Verificar colisiones
        while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
    
    def get_absolute_url(self):
        """URL absoluta del post (compatible con sitemap)"""
        return reverse('blog:post_detail', args=[self.slug])
    
    @property
    def image_url(self):
        """URL de la imagen destacada o placeholder"""
        if self.featured_image and self.featured_image.file:
            return self.featured_image.file.url
        return '/static/images/placeholder.png'
    
    @property
    def webp_image_url(self):
        """URL WebP de la imagen (con fallback a JPG)"""
        if self.featured_image:
            url = self.featured_image.get_webp_url()
            if url:
                return url
        return self.image_url
    
    def __str__(self):
        return self.title


class SocialMetadata(models.Model):
    """
    Metadata de red social para posts tipo social_repost.
    
    Relación OneToOne: un Post tiene exactamente UN embed de red social.
    Nota: El OneToOneField ya garantiza unicidad por post, por lo que 
    unique_together es redundante. Si se necesita soporte multi-plataforma
    en el futuro, migrar a ForeignKey.
    """
    
    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('tiktok', 'TikTok'),
        ('youtube', 'YouTube'),
        ('linkedin', 'LinkedIn'),
        ('x', 'X (Twitter)'),
    ]
    
    post = models.OneToOneField(
        Post,
        on_delete=models.CASCADE,
        related_name='social_metadata',
        help_text="Post al que pertenece este metadata"
    )
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        help_text="Red social de origen"
    )
    original_url = models.URLField(
        help_text="URL del post original en la red social"
    )
    embed_code = models.TextField(
        blank=True,
        help_text="Código HTML del embed (iframe)"
    )
    embed_url = models.URLField(
        blank=True,
        help_text="URL del embed (si aplica)"
    )
    captured_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha de captura del embed"
    )
    
    class Meta:
        verbose_name = "Social Media Post"
        verbose_name_plural = "Social Media Posts"
    
    def __str__(self):
        return f"{self.get_platform_display()} — {self.post.title}"
