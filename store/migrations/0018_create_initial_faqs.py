# Generated data migration to create 20 initial technical FAQs for AEO optimization

from django.db import migrations

def create_initial_faqs(apps, schema_editor):
    FAQCategory = apps.get_model('store', 'FAQCategory')
    FAQ = apps.get_model('store', 'FAQ')
    SubCategory = apps.get_model('category', 'SubCategory')

    # Categories
    cat_buloneria, _ = FAQCategory.objects.get_or_create(name="Bulonería y Fijaciones", defaults={'order': 1})
    cat_herramientas, _ = FAQCategory.objects.get_or_create(name="Herramientas Profesionales", defaults={'order': 2})
    cat_soldadura, _ = FAQCategory.objects.get_or_create(name="Soldadura y Abrasivos", defaults={'order': 3})
    cat_general, _ = FAQCategory.objects.get_or_create(name="Compras, Logística y Facturación", defaults={'order': 4})

    # Subcategories lookup (safe fallback if slug doesn't exist)
    sub_bulones = SubCategory.objects.filter(slug='bulones-y-tornillos').first()
    sub_herramientas = SubCategory.objects.filter(slug='herramientas-electricas').first()

    # FAQs data
    faqs_data = [
        # 1. Bulonería y Fijaciones
        {
            'category': cat_buloneria,
            'question': "¿Cuál es la diferencia entre un bulón grado 8.8 y uno de grado 10.9?",
            'answer': "La diferencia radica en la resistencia a la tracción y al límite elástico. Un bulón grado 8.8 tiene una resistencia de 80 kg/mm² (800 MPa), mientras que uno de grado 10.9 resiste 100 kg/mm² (1000 MPa). Los grado 10.9 se usan en estructuras metálicas de alta exigencia, chasis y maquinaria pesada que requiere mayor torque de apriete sin deformación.",
            'subcategory': sub_bulones,
            'order': 1
        },
        {
            'category': cat_buloneria,
            'question': "¿Qué roscas son comunes en bulonería y cuándo usar UNC o UNF?",
            'answer': "Las roscas principales son la rosca métrica (estándar DIN/ISO) e imperial (UNC/UNF). UNC (coarse, rosca gruesa) es la más común por su rapidez de montaje y resistencia al barrido en materiales blandos. UNF (fine, rosca fina) tiene un paso más angosto, proporcionando mayor resistencia a la tracción y menor tendencia al aflojamiento por vibración, ideal para automotores y maquinaria agrícola.",
            'subcategory': sub_bulones,
            'order': 2
        },
        {
            'category': cat_buloneria,
            'question': "¿Cómo elijo el tarugo o anclaje correcto según el tipo de pared?",
            'answer': "Para ladrillo común o hueco, se utilizan tarugos de nylon tipo UX o con tope que se expanden o anudan. Para hormigón macizo o piedra, se recomiendan anclajes metálicos de expansión (tipo cuña o camisa). Para placas de yeso (Durlock), se deben usar tarugos autoperforantes o tipo paraguas metálico que distribuyen el peso en la cara posterior.",
            'subcategory': None,
            'order': 3
        },
        {
            'category': cat_buloneria,
            'question': "¿Qué es el tratamiento superficial pavonado en un tornillo?",
            'answer': "El pavonado es un proceso de oxidación química superficial que le da al acero un color negro mate. Aporta una leve resistencia a la corrosión en interiores y previene el desgaste inicial, pero para intemperie o ambientes húmedos se debe optar por tratamientos de mayor protección como el galvanizado electrolítico o el galvanizado en caliente.",
            'subcategory': sub_bulones,
            'order': 4
        },
        {
            'category': cat_buloneria,
            'question': "¿Cuál es el torque recomendado para apretar un tornillo de acero inoxidable?",
            'answer': "El acero inoxidable (generalmente A2-70 o A4-80) es más dúctil que el acero al carbono templado y tiende a engranarse (galvanizado por fricción). Por ello, el torque de apriete debe ser menor (por ejemplo, para un tornillo M10 A2-70, unos 22 Nm) y es altamente recomendable utilizar un lubricante anti-engrane a base de níquel o cobre durante el montaje.",
            'subcategory': sub_bulones,
            'order': 5
        },
        {
            'category': cat_buloneria,
            'question': "¿Cuándo se debe usar una arandela Grower (arandela de presión)?",
            'answer': "La arandela Grower se utiliza bajo la tuerca o cabeza del bulón para evitar que la unión roscada se afloje debido a vibraciones moderadas o dilatación térmica. Al ajustarse, las puntas del resorte helicoidal muerden las superficies, ejerciendo una tensión elástica constante que mantiene apretados los filetes de la rosca.",
            'subcategory': sub_bulones,
            'order': 6
        },
        {
            'category': cat_buloneria,
            'question': "¿Qué significa la especificación de rosca en milímetros frente a pulgadas?",
            'answer': "La bulonería métrica (DIN/ISO) especifica el diámetro en milímetros (ej. M8) y el paso de rosca también en milímetros (distancia entre crestas, ej. 1.25 mm). La bulonería en pulgadas (SAE/UNC/UNF) indica el diámetro en fracciones de pulgada (ej. 3/8\") y el paso en número de hilos por pulgada (TPI, ej. 16 hilos). Nunca se deben forzar roscas diferentes, ya que daña irreversiblemente los filetes.",
            'subcategory': sub_bulones,
            'order': 7
        },

        # 2. Herramientas Profesionales
        {
            'category': cat_herramientas,
            'question': "¿Qué diferencia hay entre un taladro percutor y un rotomartillo?",
            'answer': "El taladro percutor usa un mecanismo de discos dentados para generar pequeños golpes de alta frecuencia, ideal para mampostería ligera y madera. El rotomartillo utiliza un pistón neumático que golpea directamente el mandril (encastre SDS-Plus o SDS-Max), generando un impacto de mucha mayor energía por golpe, diseñado para perforar y cincelar hormigón armado de manera rápida y sin esfuerzo para el operador.",
            'subcategory': sub_herramientas,
            'order': 1
        },
        {
            'category': cat_herramientas,
            'question': "¿Qué medidas de seguridad se deben tomar al operar una amoladora angular?",
            'answer': "Es obligatorio utilizar elementos de protección personal (EPP): antiparras de seguridad (o máscara facial), guantes de cuero, protector auditivo y delantal de lona. Nunca se debe retirar la guarda protectora de la máquina. El disco debe colocarse en la posición correcta según su sentido de giro, y se debe utilizar el disco adecuado para cada tarea (corte fino, desbaste o flap), asegurándose de no superar la velocidad máxima (RPM) indicada en el mismo.",
            'subcategory': None,
            'order': 2
        },
        {
            'category': cat_herramientas,
            'question': "¿Qué ventajas tienen las herramientas inalámbricas con motor Brushless (sin carbones)?",
            'answer': "Los motores Brushless eliminan la fricción física de los carbones, lo que reduce el sobrecalentamiento y el mantenimiento casi a cero. Esto se traduce en una mayor eficiencia energética (hasta un 50% más de autonomía de batería por carga), mayor potencia a menor tamaño y una vida útil de la herramienta significativamente superior comparada con los modelos con carbones convencionales.",
            'subcategory': sub_herramientas,
            'order': 3
        },
        {
            'category': cat_herramientas,
            'question': "¿Qué significan las marcas Bahco, Bremen y Bosch para un profesional?",
            'answer': "Son marcas líderes en el rubro industrial y profesional: Bahco es sinónimo de herramientas manuales de calidad premium (llaves ajustables, destornilladores, alicates); Bremen ofrece una excelente relación calidad-precio en juegos de tubos de fuerza, llaves de cromo vanadio y herramientas de taller; y Bosch es el referente en herramientas eléctricas profesionales con alta durabilidad y servicio técnico garantizado.",
            'subcategory': None,
            'order': 4
        },
        {
            'category': cat_herramientas,
            'question': "¿Cómo se realiza el mantenimiento básico de las llaves de cromo vanadio?",
            'answer': "Para prevenir la oxidación y prolongar la vida útil, se deben limpiar las llaves manuales después de cada uso con un paño seco para retirar restos de grasa, aceite o humedad. Ocasionalmente, se les puede aplicar una fina capa de lubricante multiuso (aceite ligero) y guardarlas en un lugar seco o dentro de sus estuches organizadores.",
            'subcategory': None,
            'order': 5
        },

        # 3. Soldadura y Abrasivos
        {
            'category': cat_soldadura,
            'question': "¿Cuál es el electrodo de soldar adecuado para herrería hogareña y chapa fina?",
            'answer': "El electrodo más recomendado y utilizado es el rutílico AWS E6013 (generalmente en diámetros de 2.0 mm o 2.5 mm). Este electrodo proporciona un arco estable, fácil encendido, pocas salpicaduras y es ideal para soldar chapas finas, perfiles estructurales y caños de hierro en cualquier posición, dejando una escoria que se desprende con facilidad.",
            'subcategory': None,
            'order': 1
        },
        {
            'category': cat_soldadura,
            'question': "¿Cuándo utilizar un electrodo E7018 de bajo hidrógeno en una obra?",
            'answer': "El electrodo básico E7018 se utiliza en estructuras sujetas a grandes esfuerzos mecánicos, recipientes a presión y uniones de aceros al carbono de alta resistencia. Al ser de bajo hidrógeno, previene el agrietamiento en frío de la soldadura. Requiere una máquina de soldar de corriente continua (DC) y los electrodos deben mantenerse secos en hornos portátiles antes de su uso.",
            'subcategory': None,
            'order': 2
        },
        {
            'category': cat_soldadura,
            'question': "¿Qué diferencia hay entre un disco de corte fino de 1 mm y un disco de desbaste?",
            'answer': "El disco de corte fino (de 1.0 mm a 1.6 mm de espesor) está diseñado exclusivamente para realizar cortes rápidos y limpios en metal o acero inoxidable, aplicando poca presión. Por motivos de seguridad, nunca debe usarse para desbastar. El disco de desbaste (generalmente de 6.0 mm o más) posee refuerzo estructural para soportar la presión lateral ejercida al pulir cordones de soldadura o rebajar cantos metálicos.",
            'subcategory': None,
            'order': 3
        },
        {
            'category': cat_soldadura,
            'question': "¿Para qué sirve un disco flap de lija y cuándo sustituye al disco de desbaste?",
            'answer': "El disco flap combina hojas de lija superpuestas sobre un soporte de fibra. Se utiliza para desbastar ligeramente y dar una terminación pulida al metal en un solo paso. Sustituye al disco de desbaste cuando se requiere un acabado superficial más suave y prolijo, o para remover pintura y óxido de manera controlada sin dañar o morder el material base.",
            'subcategory': None,
            'order': 4
        },

        # 4. Compras, Logística y Facturación
        {
            'category': cat_general,
            'question': "¿Cómo solicito un presupuesto formal por WhatsApp?",
            'answer': "Es sumamente rápido: haz clic en el botón de WhatsApp de nuestra web para iniciar un chat directo con nuestro mostrador. Envíanos las medidas, cantidad, grados o normas de los bulones o herramientas que necesitas. Nuestro equipo técnico responderá en menos de 15 minutos con un presupuesto detallado que incluye precios y disponibilidad de stock.",
            'subcategory': None,
            'order': 1
        },
        {
            'category': cat_general,
            'question': "¿Realizan envíos a las provincias vecinas de Corrientes, Formosa y Misiones?",
            'answer': "Sí, realizamos despachos diarios a todo el NEA. Trabajamos habitualmente con transportes de carga de confianza en la región como Niclis, Snaider, Vía Cargo y Andreani. El costo de envío se cotiza en conjunto con tu pedido según el volumen y peso de la mercadería. También puedes optar por retirar sin costo en nuestro local de Av. Alvear 1301, Resistencia.",
            'subcategory': None,
            'order': 2
        },
        {
            'category': cat_general,
            'question': "¿Emiten Factura A para empresas y constructoras en Argentina?",
            'answer': "Sí, al ser Responsables Inscriptos emitimos Factura A y Factura B según corresponda. Al momento de confirmar tu pedido o solicitar el presupuesto por WhatsApp o email, envíanos tu CUIT y constancia de inscripción en AFIP / ATP Chaco para realizar la facturación correspondiente de manera ágil.",
            'subcategory': None,
            'order': 3
        },
        {
            'category': cat_general,
            'question': "¿Tienen venta por peso (a granel) en bulonería estándar?",
            'answer': "Sí, disponemos de venta a granel por peso en kilogramos para bulonería estándar (tornillos hexagonales de hierro, arandelas planas, Grower, tuercas de hierro zincado), lo cual reduce significativamente el costo unitario para compras en volumen. Para medidas especiales o bulonería de alta resistencia (grado 8.8, 10.9, acero inoxidable), la venta se realiza por unidades o cajas cerradas.",
            'subcategory': None,
            'order': 4
        }
    ]

    for data in faqs_data:
        FAQ.objects.get_or_create(
            question=data['question'],
            defaults={
                'category': data['category'],
                'answer': data['answer'],
                'subcategory': data['subcategory'],
                'order': data['order'],
                'is_active': True
            }
        )

def reverse_initial_faqs(apps, schema_editor):
    FAQCategory = apps.get_model('store', 'FAQCategory')
    FAQ = apps.get_model('store', 'FAQ')

    FAQ.objects.all().delete()
    FAQCategory.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('store', '0017_add_cta_band_section_type'),
    ]

    operations = [
        migrations.RunPython(create_initial_faqs, reverse_initial_faqs),
    ]
