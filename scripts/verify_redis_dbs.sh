#!/bin/bash
# ============================================
# Verificar qué DBs de Redis usa el ERP
# ============================================
# Ejecutar en el VPS para ver qué bases de datos
# de Redis están en uso por el ERP
# ============================================

echo "🔍 Verificando bases de datos Redis en uso..."
echo ""

for db in {0..15}; do
    keys=$(redis-cli -n $db DBSIZE | awk '{print $2}')
    if [ "$keys" -gt 0 ]; then
        echo "✅ DB $db: $keys keys"
        echo "   Primeras 5 keys:"
        redis-cli -n $db KEYS '*' | head -5 | sed 's/^/   - /'
        echo ""
    else
        echo "⚪ DB $db: vacía"
    fi
done

echo ""
echo "📋 Recomendación:"
echo "   - Si el ERP usa DB 0 y 1, asignar a la web: 3, 4, 5"
echo "   - Si el ERP usa DB 0, 1, 2, asignar a la web: 3, 4, 5"
echo "   - Actualizar .env con los valores correctos"
