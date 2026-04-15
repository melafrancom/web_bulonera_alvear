"""Cart API Serializers"""
from rest_framework import serializers
from cart.models import Cart, CartItem
from store.models import Variation


class VariationSerializer(serializers.ModelSerializer):
    """Serializer para Variation (usado en CartItem)"""
    
    class Meta:
        model = Variation
        fields = ['id', 'variation_category', 'variation_value']


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer para CartItem"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()
    variations = VariationSerializer(source='variation', many=True, read_only=True)
    sub_total = serializers.ReadOnlyField()
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'product_name', 'product_slug', 'product_image',
            'quantity', 'purchase_price', 'sub_total', 'variations', 'is_active'
        ]
        read_only_fields = ['id', 'purchase_price', 'sub_total']
    
    def get_product_image(self, obj):
        """Obtiene la URL de la imagen del producto"""
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.product.image_url)
        return obj.product.image_url


class AddToCartSerializer(serializers.Serializer):
    """Serializer para agregar productos al carrito"""
    product_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(default=1, min_value=1)
    variations = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    
    def validate_quantity(self, value):
        """Valida que la cantidad sea positiva"""
        if value < 1:
            raise serializers.ValidationError("La cantidad debe ser mayor a 0")
        return value


class UpdateCartItemSerializer(serializers.Serializer):
    """Serializer para actualizar cantidad de un item"""
    quantity = serializers.IntegerField(min_value=1, required=True)
    
    def validate_quantity(self, value):
        """Valida que la cantidad sea positiva"""
        if value < 1:
            raise serializers.ValidationError("La cantidad debe ser mayor a 0")
        return value


class CartSummarySerializer(serializers.Serializer):
    """Serializer para resumen del carrito"""
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    cart_count = serializers.IntegerField(read_only=True)
