"""Blog Web URLs - Traditional HTML routes"""
from django.urls import path
from blog.web.views import BlogListView, BlogDetailView

app_name = 'blog'

urlpatterns = [
    path('', BlogListView.as_view(), name='post_list'),
    path('<slug:slug>/', BlogDetailView.as_view(), name='post_detail'),
]
