"""Blog API Serializers - DRF serializers"""
from rest_framework import serializers
from blog.models import Post, PostTag, SocialMetadata


class PostTagSerializer(serializers.ModelSerializer):
    """Serializer para PostTag"""
    
    class Meta:
        model = PostTag
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id', 'slug']


class SocialMetadataSerializer(serializers.ModelSerializer):
    """Serializer para SocialMetadata"""
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    
    class Meta:
        model = SocialMetadata
        fields = ['platform', 'platform_display', 'original_url', 'embed_url', 'embed_code', 'captured_at']
        read_only_fields = ['captured_at']


class PostListSerializer(serializers.ModelSerializer):
    """Serializer para lista de posts (lightweight)"""
    tags = PostTagSerializer(many=True, read_only=True)
    post_type_display = serializers.CharField(source='get_post_type_display', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 'post_type', 'post_type_display',
            'image_url', 'webp_image_url', 'published_date', 'views_count',
            'tags', 'author_name', 'created_date'
        ]
        read_only_fields = fields


class PostDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para un post individual"""
    tags = PostTagSerializer(many=True, read_only=True)
    social_metadata = SocialMetadataSerializer(read_only=True)
    post_type_display = serializers.CharField(source='get_post_type_display', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    image_alt = serializers.CharField(read_only=True)
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'content', 'excerpt', 'post_type', 'post_type_display',
            'image_url', 'webp_image_url', 'image_alt', 'published_date',
            'views_count', 'tags', 'author_name', 'created_date', 'modified_date',
            'meta_title', 'meta_description', 'meta_keywords', 'social_metadata'
        ]
        read_only_fields = fields


class PostRelatedSerializer(serializers.ModelSerializer):
    """
    Serializer liviano para posts relacionados.
    Solo expone los campos necesarios para una card de preview.
    No incluye content ni social_metadata (evita N+1 queries).
    """
    tags = PostTagSerializer(many=True, read_only=True)
    post_type_display = serializers.CharField(source='get_post_type_display', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 'post_type', 'post_type_display',
            'image_url', 'webp_image_url', 'image_alt', 'published_date',
            'views_count', 'tags'
        ]
        read_only_fields = fields
