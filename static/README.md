# 📁 Directorio static — Cerebro Local

## 🎯 Propósito
Este directorio organiza los recursos estáticos públicos del frontend (hojas de estilo CSS, fuentes, librerías de JavaScript e imágenes estáticas del tema) antes de ser recopilados y consolidados para producción.

## 🕸️ Estructura y Archivos

```
static/
├── css/
│   ├── base.css               ← Archivo origen de estilos generales
│   ├── tailwind.css           ← Archivo de entrada de directivas Tailwind
│   └── tailwind.min.css       ← CSS final compilado y minificado para producción
│
├── fonts/                     ← Fuentes tipográficas locales del sitio
├── js/                        ← Scripts de comportamiento e interactividad del cliente
└── images/                    ← Logos, placeholders e iconos fijos del sistema
```

## 🕸️ Flujo de Compilación y Distribución

```
Desarrollo (static/css/tailwind.css)
        │
        ▼ (npm run build:css)
Compilación y Minificación (static/css/tailwind.min.css)
        │
        ▼ (python manage.py collectstatic)
Consolidación en Producción (/var/www/bulonera/staticfiles/)
        │
        ▼ (Servido directamente por OpenLiteSpeed)
Navegador del Cliente (Cache: 1 año)
```

## ⚙️ Pipeline de Compilación TailwindCSS
En producción, el contenedor de compilación (`Stage 1` en `Dockerfile.production`) ejecuta la compilación de TailwindCSS antes de instanciar la imagen de Python:
```dockerfile
# Stage 1: Build Tailwind CSS
FROM node:20-slim AS builder
...
COPY . .
RUN npm run build:css
```
Esto busca todas las clases CSS utilizadas en los templates HTML y genera el archivo minificado `/app/static/css/tailwind.min.css`.

## 📝 Notas de Detalle (Obsidian Vault)
- **Producción vs Desarrollo**: En producción, OpenLiteSpeed sirve el directorio consolidado `staticfiles/` de forma directa sin pasar por el contenedor de Django, aplicando cabeceras HTTP de expiración agresivas (1 año de caché) para máxima velocidad de respuesta.
- **collectstatic**: En producción, no se modifica la carpeta `static/` del repositorio; las vistas leen los estáticos consolidados en el volumen `/var/www/bulonera/staticfiles/`.
