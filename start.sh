#!/bin/bash

# Thu thập các tệp tĩnh
# (sao chép các tệp tĩnh từ ứng dụng vào thư mục chung để phục vụ)
# python manage.py collectstatic --no-input

# Tạo các tệp migrate để đồng bộ hóa cơ sở dữ liệu
python manage.py makemigrations

# Thực thi các tệp migrate để áp dụng thay đổi vào cơ sở dữ liệu
python manage.py migrate

# Khởi chạy server Django trên cổng 8000
python manage.py runserver 0.0.0.0:8000
