import json
import re
from rest_framework.parsers import MultiPartParser
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
        
class NestedMultiPartParser(MultiPartParser):
    """
    Custom parser để hỗ trợ nested FormData gửi từ Frontend, bao gồm cả file và dữ liệu dạng JSON.
    """

    def parse(self, stream, media_type=None, parser_context=None):
        parsed_data = super().parse(stream, media_type, parser_context)
        nested_data = {}   # Chứa dữ liệu text (không có file)

        # Xử lý dữ liệu text (không phải file)
        for key, value in parsed_data.data.items():
            keys = self._parse_keys(key)
            self._set_nested_value(nested_data, keys, value)
        
        # Xử lý dữ liệu file (chỉ có file)
        for key, value in parsed_data.files.items():
            keys = self._parse_keys(key)
            self._set_nested_value(nested_data, keys, value)
        return nested_data

    def _parse_keys(self, key):
        """ Chuyển `a[0][b]` thành [a, 0, b] """
        parts = re.findall(r'\w+|\[\d+\]', key)
        return [int(p[1:-1]) if p.startswith('[') else p for p in parts]

    def _set_nested_value(self, data, keys, value):
        """ Đệ quy để set giá trị vào dictionary lồng nhau, hỗ trợ list """
        d = data
        for i, k in enumerate(keys[:-1]):
            if isinstance(k, int):  # Nếu key là số, đảm bảo data là list
                while len(d) <= k:
                    d.append({})
                d = d[k]
            else:
                if k not in d:
                    d[k] = [] if isinstance(keys[i + 1], int) else {}
                d = d[k]

        # Nếu giá trị là JSON string, parse thành object
        if isinstance(value, str):
            try:
                value = json.loads(value)  # Nếu là JSON, parse thành dict/list
            except ValueError:
                pass  # Không phải JSON thì giữ nguyên
        
        # Kiểm tra nếu là file tải lên (InMemoryUploadedFile hoặc TemporaryUploadedFile)
        if isinstance(value, (InMemoryUploadedFile, TemporaryUploadedFile)):
            d[keys[-1]] = value 

        # Đảm bảo giá trị không bị ghi đè nếu đã tồn tại (dữ liệu JSON hoặc text)
        elif isinstance(d, dict) and keys[-1] in d:
            if isinstance(d[keys[-1]], dict):
                d[keys[-1]].update(value)
            else:
                d[keys[-1]] = [d[keys[-1]], value] if not isinstance(d[keys[-1]], list) else d[keys[-1]] + [value]
        else:
            d[keys[-1]] = value
