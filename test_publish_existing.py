import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_bulonera.settings.local')
django.setup()

from blog.models import Post
from account.models import Account

try:
    admin = Account.objects.filter(is_admin=True).first()
    if not admin:
        print("No admin found")
    else:
        title = "Post de prueba publicación Admin " + str(os.getpid())
        # Crear post borrador primero
        post = Post.objects.create(
            title=title,
            content="Contenido",
            author=admin,
            is_published=False
        )
        print(f"Post creado (borrador): {post.id}, is_published: {post.is_published}")
        
        # Ahora intentar publicar como lo haría el admin
        post.is_published = True
        post.save()
        
        post.refresh_from_db()
        print(f"Post actualizado: {post.id}, is_published: {post.is_published}, date: {post.published_date}")
        
        if post.is_published:
            print("PUBLICADO OK")
        else:
            print("FALLO EN PUBLICACIÓN")

except Exception as e:
    print(f"Error: {e}")
