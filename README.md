# Ecommerce  
<p align="center">
  <img src="https://github.com/melafrancom/web_bulonera_alvear/blob/master/bulonera/static/images/logo02.png" alt="Logo" style="width: 30%; max-width: 200px;">
</p>
<h5 align="center">Bulonera Alvear| Bulonería y Ferretería.</h5>

Bulonera Alvear es un proyecto de e-commerce desarrollado en Django para mi empresa familiar, que ofrece una experiencia de compra en línea dinámica y completa. Descubre una amplia variedad de productos, gestiona tus compras y maneja tu cuenta a tu gusto, todo en un sitio web intuitivo y fácil de usar.

Bulonera Alvear | ¡Construyendo el futuro, tornillo a tornillo!

Estructura del Proyecto
web/
├── bulonera/                  # Proyecto principal
│   ├── account/              # Gestión de usuarios y autenticación
│   ├── bulonera/             # Configuración principal del proyecto
│   ├── cart/                 # Carrito de compras
│   ├── category/             # Gestión de categorías y subcategorías
│   ├── contact/             # Formularios de contacto
│   ├── orders/              # Gestión de pedidos
│   └── store/               # Catálogo de productos y lógica de negocio
├── entornos/                # Entornos virtuales
├── desktop.ini
└── README.md

Descripción General
  La aplicación principal 'bulonera' contiene la configuración central del proyecto y maneja las funcionalidades básicas del sitio web.

Características Clave
  Configuración de base de datos en MariaDB (MySQL)
  Soporte multilenguaje (es-ar)
  Manejo de archivos estáticos y media
  Configuración de sesiones
  Integración con Meta Pixel y Google Merchant

Variables de Entorno Requeridas
  SECRET_KEY=your_secret_key
  DEBUG=True
  DB_NAME=bulonera_db
  DB_USER=your_db_user
  DB_PASSWORD=your_db_password
  DB_HOST=localhost
  WHATSAPP_NUMBER=your_whatsapp
  SITE_URL=your_site_url
  META_PIXEL_ID=your_pixel_id

Vistas Principales (views.py)

Home View
Características:
  Muestra productos más vendidos
  Productos más buscados (global y por usuario)
  Carrusel de imágenes seleccionadas por el admin
  Categorías destacadas
  Productos por categoría

# Account
La app 'account' maneja la autenticación y gestión de usuarios en Bulonera Alvear, implementando un sistema personalizado de usuarios con perfiles extendidos y funcionalidades de autenticación por email.

Características Principales

Sistema de Autenticación
  Autenticación por email
  Activación de cuenta por email
  Recuperación de contraseña
  Sesiones persistentes

Panel de Usuario
  Dashboard personalizado
  Gestión de perfil
  Historial de pedidos
  Estadísticas de compras

Integración con Carrito
  Persistencia de carrito entre sesiones
  Fusión de carritos al iniciar sesión
  Gestión de productos guardados

# Cart
Descripción General
La app 'cart' gestiona el carrito de compras en Bulonera Alvear, permitiendo a usuarios registrados y no registrados agregar productos, gestionar cantidades y proceder al checkout.

Características Principales

Gestión de Precios
  Manejo de precios regulares y de oferta
  Almacenamiento del precio al momento de la compra
  Cálculo automático de subtotales

Integración de Usuarios
  Soporte para usuarios anónimos y registrados
  Persistencia del carrito entre sesiones
  Fusión de carritos al iniciar sesión

Variaciones de Productos
  Soporte para múltiples variaciones
  Validación de combinaciones
  Gestión de stock

Consideraciones
  El carrito mantiene los precios al momento de agregar productos
  Soporta productos con y sin variaciones
  Maneja automáticamente la fusión de carritos
  Validación de stock en tiempo real

# Category
Descripción General
La app 'category' gestiona la estructura jerárquica de categorías y subcategorías de productos en Bulonera Alvear, proporcionando una organización clara del catálogo y navegación intuitiva.

Características Principales
Estructura Jerárquica
  Categorías principales
  Subcategorías relacionadas
  URLs amigables (slugs)

Gestión de Imágenes
  Procesamiento automático de nombres
  Limpieza de caracteres especiales
  Organización en directorios

Categorías Destacadas
  Posicionamiento personalizable
  Control de visibilidad
  Ordenamiento flexible

Integración con Otras Apps
  Con Store
    Filtrado de productos por categoría/subcategoría
    URLs para listados de productos
    Navegación jerárquica
  Con FAQ
    FAQs específicas por subcategoría
    Gestión de preguntas frecuentes
    Organización de contenido informativo
Uso
  Obtener Categorías

# Contact
Descripción General
La app 'contact' maneja el sistema de contacto de Bulonera Alvear, permitiendo a los usuarios enviar consultas a través de correo electrónico o WhatsApp.

Características Principales
  Sistema de Contacto Dual
    Opción de contacto por email
    Integración con WhatsApp
    Formulario unificado
  Gestión de Mensajes
    Almacenamiento en base de datos
    Panel administrativo
    Historial de contactos
  Notificaciones
    Envío automático de emails
    Mensajes de confirmación
    Redirección inteligente

# Orders
Descripción General
La app 'orders' gestiona el proceso de pedidos en Bulonera Alvear, manejando el flujo completo desde la creación del pedido hasta su finalización, con integración a WhatsApp y sistema de pagos.

Características Principales
  Sistema de Pagos
    Integración con múltiples métodos de pago
    Registro de transacciones
    Validación de pagos
    Estado de pagos en tiempo real
  Integración con WhatsApp
    Generación automática de mensajes
    Enlaces directos a WhatsApp Business
    Resumen detallado del pedido
    Formato personalizado de mensajes
  Gestión de Pedidos
    Panel administrativo completo
    Estados de pedido configurables
    Historial de transacciones
    Seguimiento de productos ordenados
Vistas Principales
  Proceso de Pedido

# Store
Descripción General
La app 'store' es el núcleo del e-commerce de Bulonera Alvear, gestionando productos, búsquedas, reseñas, FAQs y la integración con plataformas de marketing digital.

Características Principales
  Gestión de Productos
    Importación masiva desde Excel/CSV
    Actualización masiva de precios
    Gestión de imágenes automática
    Sistema de variaciones
    Control de stock
  Sistema de Búsqueda
    Búsqueda por texto
    Filtros por categoría/subcategoría
    Tracking de búsquedas populares
    Historial de búsquedas por usuario

  Procesamiento automático de imágenes
  - Generación de thumbnails
  - Conversión a WebP
  - Optimización de tamaños
  - Mantenimiento de proporción

Integración con Marketing
  Meta Pixel integration
  Google Merchant feeds
  SEO optimizado
  Rich snippets
