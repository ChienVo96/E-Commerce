from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

class UserPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 100
    page_size_query_param = 'page_size'
    
    def get_paginated_response(self, data):
        # Tính toán dải số trang
        current_page = self.page.number
        total_pages = self.page.paginator.num_pages
        pagination = {
            'current_page': current_page,
            'total_pages': total_pages,
        }
        return Response({
            'pagination': pagination,
            'users': data
        })
    
class CategoryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        # Tính toán dải số trang
        current_page = self.page.number
        total_pages = self.page.paginator.num_pages
        pagination = {
            "current_page": current_page,
            "total_pages": total_pages,
        }
        return Response({"pagination": pagination, "data": data})

class PromotionPagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = 'page_size'
    
    def get_paginated_response(self, data):
        # Tính toán dải số trang
        current_page = self.page.number
        total_pages = self.page.paginator.num_pages
        pagination = {
            'current_page': current_page,
            'total_pages': total_pages,
        }
        return Response({
            'pagination': pagination,
            'promotions': data
        })
    
class ProductPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 1000
    page_size_query_param = 'page_size'
    
    def get_paginated_response(self, data):
        # Tính toán dải số trang
        current_page = self.page.number
        total_pages = self.page.paginator.num_pages
        pagination = {
            'current_page': current_page,
            'total_pages': total_pages,
        }
        return Response({
            'pagination': pagination,
            'products': data
        })
    
class VariantPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 100
    page_size_query_param = 'page_size'
    
    def get_paginated_response(self, data):
        # Tính toán dải số trang
        current_page = self.page.number
        total_pages = self.page.paginator.num_pages
        pagination = {
            'current_page': current_page,
            'total_pages': total_pages,
        }
        return Response({
            'pagination': pagination,
            'variants': data
        })
    
class CommentPagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = 'page_size'
    
    def get_paginated_response(self, data):
        # Tính toán dải số trang
        current_page = self.page.number
        total_pages = self.page.paginator.num_pages
        pagination = {
            'current_page': current_page,
            'total_pages': total_pages,
        }
        return Response({
            'pagination': pagination,
            'comments': data
        })
    
class ReviewPagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = 'page_size'
    
    def get_paginated_response(self, data):
        # Tính toán dải số trang
        current_page = self.page.number
        total_pages = self.page.paginator.num_pages
        pagination = {
            'current_page': current_page,
            'total_pages': total_pages,
        }
        return Response({
            'pagination': pagination,
            'reviews': data
        })
    