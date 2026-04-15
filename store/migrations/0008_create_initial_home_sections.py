# Generated data migration for initial home sections

from django.db import migrations


def create_initial_sections(apps, schema_editor):
    """Create initial home sections replicating current hard-coded structure"""
    HomeSection = apps.get_model('store', 'HomeSection')
    Category = apps.get_model('category', 'Category')

    # Define initial sections
    sections_data = [
        {
            'title': 'Carrusel Principal',
            'section_type': 'hero',
            'position': 1,
            'is_active': True,
        },
        {
            'title': 'Acceso Rápido',
            'section_type': 'quick_access',
            'position': 2,
            'is_active': True,
        },
        {
            'title': 'Los más vendidos',
            'section_type': 'product_carousel',
            'source_type': 'bestsellers',
            'position': 3,
            'max_products': 20,
            'is_active': True,
        },
        {
            'title': 'Todas las Categorías',
            'section_type': 'categories',
            'position': 4,
            'is_active': True,
        },
        {
            'title': 'Lo que más buscan',
            'section_type': 'product_carousel',
            'source_type': 'most_searched',
            'position': 5,
            'max_products': 12,
            'is_active': True,
        },
        {
            'title': 'Cómo Comprar',
            'section_type': 'how_to_buy',
            'position': 10,
            'is_active': True,
        },
    ]

    # Create sections
    for section_data in sections_data:
        # Extract FK references
        category_id = section_data.pop('category_id', None)
        
        section, created = HomeSection.objects.get_or_create(
            title=section_data['title'],
            section_type=section_data['section_type'],
            defaults={
                'position': section_data.get('position', 0),
                'source_type': section_data.get('source_type'),
                'max_products': section_data.get('max_products', 12),
                'is_active': section_data.get('is_active', True),
                'category_id': category_id,
            }
        )
        
        if created:
            print(f"Created section: {section.title}")


def reverse_initial_sections(apps, schema_editor):
    """Remove initial sections on reverse migration"""
    HomeSection = apps.get_model('store', 'HomeSection')
    
    # Remove sections by title (safe approach)
    titles = [
        'Carrusel Principal',
        'Acceso Rápido',
        'Los más vendidos',
        'Todas las Categorías',
        'Lo que más buscan',
        'Cómo Comprar',
    ]
    
    for title in titles:
        HomeSection.objects.filter(title=title).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0007_homesection_promobanner_homesectionproduct'),
    ]

    operations = [
        migrations.RunPython(create_initial_sections, reverse_initial_sections),
    ]
