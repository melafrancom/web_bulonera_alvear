"""Orders API Serializers"""
from rest_framework import serializers
from orders.models import Order, Payment, OrderProduct
from store.models import Variation


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer para Payment"""
    
    class Meta:
        model = Payment
        fields = ['id', 'payment_id', 'payment_method', 'amount_id', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class VariationSerializer(serializers.ModelSerializer):
    """Serializer para Variation (usado en OrderProduct)"""
    
    class Meta:
        model = Variation
        fields = ['id', 'variation_category', 'variation_value']


class OrderProductSerializer(serializers.ModelSerializer):
    """Serializer para OrderProduct"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()
    variations = VariationSerializer(source='variation', many=True, read_only=True)
    sub_total = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderProduct
        fields = [
            'id', 'product', 'product_name', 'product_slug', 'product_image',
            'quantity', 'purchase_price', 'sub_total', 'variations',
            'ordered', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_product_image(self, obj):
        """Obtiene la URL de la imagen del producto"""
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.product.image_url)
        return obj.product.image_url
    
    def get_sub_total(self, obj):
        """Calcula el subtotal del producto"""
        return obj.purchase_price * obj.quantity


class OrderSerializer(serializers.ModelSerializer):
    """Serializer para Order con productos anidados"""
    payment = PaymentSerializer(read_only=True)
    products = OrderProductSerializer(
        source='orderproduct_set',
        many=True,
        read_only=True
    )
    full_name = serializers.SerializerMethodField()
    full_address = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'full_name', 'first_name', 'last_name',
            'phone', 'email', 'address_line_1', 'address_line_2', 'country',
            'city', 'state', 'full_address', 'order_note', 'order_total',
            'status', 'status_display', 'payment', 'products', 'is_ordered',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order_number', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        """Obtiene el nombre completo"""
        return obj.full_name()
    
    def get_full_address(self, obj):
        """Obtiene la dirección completa"""
        return obj.full_address()


class OrderListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de órdenes"""
    full_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'full_name', 'order_total',
            'status', 'status_display', 'product_count',
            'is_ordered', 'created_at'
        ]
        read_only_fields = ['id', 'order_number', 'created_at']
    
    def get_full_name(self, obj):
        """Obtiene el nombre completo"""
        return obj.full_name()
    
    def get_product_count(self, obj):
        """Cuenta los productos de la orden"""
        return obj.orderproduct_set.count()


class CreateOrderSerializer(serializers.Serializer):
    """Serializer para crear una orden desde el carrito"""
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=25)
    email = serializers.EmailField()
    address_line_1 = serializers.CharField(max_length=100)
    address_line_2 = serializers.CharField(max_length=100, required=False, allow_blank=True)
    country = serializers.CharField(max_length=50)
    city = serializers.CharField(max_length=50)
    state = serializers.CharField(max_length=5)
    order_note = serializers.CharField(max_length=100, required=False, allow_blank=True)


class ProcessPaymentSerializer(serializers.Serializer):
    """Serializer para procesar un pago"""
    order_number = serializers.CharField(max_length=30)
    payment_id = serializers.CharField(max_length=100)
    payment_method = serializers.CharField(max_length=100)
    status = serializers.CharField(max_length=100)
    
    def validate_payment_method(self, value):
        """Valida el método de pago"""
        valid_methods = ['Credit Card', 'Debit Card', 'PayPal', 'WhatsApp', 'Transfer']
        if value not in valid_methods:
            raise serializers.ValidationError(f"Método de pago inválido. Opciones: {', '.join(valid_methods)}")
        return value
