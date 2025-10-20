import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List

class TestDataGenerator:
    """Generate test data for various types and scenarios."""
    
    def __init__(self):
        self.string_templates = [
            "test_string_{}",
            "example_{}",
            "sample_{}",
            "data_{}",
            "value_{}"
        ]
    
    def generate_data(self, data_type: str, constraints: Dict = None) -> Any:
        """Generate test data based on type and constraints."""
        constraints = constraints or {}
        
        if data_type.lower() in ["str", "string"]:
            return self.generate_string(**constraints)
        elif data_type.lower() in ["int", "integer"]:
            return self.generate_integer(**constraints)
        elif data_type.lower() in ["float", "double", "decimal"]:
            return self.generate_float(**constraints)
        elif data_type.lower() in ["bool", "boolean"]:
            return self.generate_boolean(**constraints)
        elif data_type.lower() in ["list", "array"]:
            return self.generate_list(**constraints)
        elif data_type.lower() in ["dict", "object", "map"]:
            return self.generate_dict(**constraints)
        elif data_type.lower() in ["date", "datetime"]:
            return self.generate_datetime(**constraints)
        elif data_type.lower() in ["email"]:
            return self.generate_email(**constraints)
        elif data_type.lower() in ["url"]:
            return self.generate_url(**constraints)
        elif data_type.lower() in ["phone", "telephone"]:
            return self.generate_phone(**constraints)
        else:
            # Default to string if type is unknown
            return self.generate_string(**constraints)
    
    def generate_string(self, min_length: int = 1, max_length: int = 10, 
                       prefix: str = "", suffix: str = "", 
                       include_numbers: bool = True, include_special: bool = False) -> str:
        """Generate a random string."""
        length = random.randint(min_length, max_length)
        
        # Choose a template
        template = random.choice(self.string_templates)
        
        # Generate base string
        if include_numbers:
            chars = string.ascii_letters + string.digits
        else:
            chars = string.ascii_letters
        
        if include_special:
            chars += "!@#$%^&*"
        
        base = ''.join(random.choice(chars) for _ in range(length))
        
        # Apply template
        result = template.format(base)
        
        # Add prefix and suffix
        return f"{prefix}{result}{suffix}"
    
    def generate_integer(self, min_value: int = 0, max_value: int = 100) -> int:
        """Generate a random integer."""
        return random.randint(min_value, max_value)
    
    def generate_float(self, min_value: float = 0.0, max_value: float = 100.0, 
                      decimal_places: int = 2) -> float:
        """Generate a random float."""
        value = random.uniform(min_value, max_value)
        return round(value, decimal_places)
    
    def generate_boolean(self, true_probability: float = 0.5) -> bool:
        """Generate a random boolean."""
        return random.random() < true_probability
    
    def generate_list(self, item_type: str = "string", min_length: int = 1, 
                     max_length: int = 5, item_constraints: Dict = None) -> List:
        """Generate a random list."""
        length = random.randint(min_length, max_length)
        item_constraints = item_constraints or {}
        
        return [
            self.generate_data(item_type, item_constraints) 
            for _ in range(length)
        ]
    
    def generate_dict(self, keys: List[str] = None, value_types: Dict = None, 
                     min_keys: int = 1, max_keys: int = 5) -> Dict:
        """Generate a random dictionary."""
        if keys is None:
            # Generate random keys
            num_keys = random.randint(min_keys, max_keys)
            keys = [f"key_{i}" for i in range(num_keys)]
        
        if value_types is None:
            # Default all values to strings
            value_types = {key: "string" for key in keys}
        
        result = {}
        for key in keys:
            value_type = value_types.get(key, "string")
            result[key] = self.generate_data(value_type)
        
        return result
    
    def generate_datetime(self, start_date: str = None, end_date: str = None, 
                         date_format: str = "%Y-%m-%d") -> str:
        """Generate a random datetime string."""
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime(date_format)
        
        if end_date is None:
            end_date = datetime.now().strftime(date_format)
        
        start = datetime.strptime(start_date, date_format)
        end = datetime.strptime(end_date, date_format)
        
        delta = end - start
        random_days = random.randint(0, delta.days)
        result_date = start + timedelta(days=random_days)
        
        return result_date.strftime(date_format)
    
    def generate_email(self, domain: str = None, username_prefix: str = "test") -> str:
        """Generate a random email address."""
        if domain is None:
            domains = ["example.com", "test.org", "sample.net", "demo.io"]
            domain = random.choice(domains)
        
        username = f"{username_prefix}_{random.randint(1, 1000)}"
        return f"{username}@{domain}"
    
    def generate_url(self, scheme: str = "https", domain: str = None, 
                    path: str = None, query_params: Dict = None) -> str:
        """Generate a random URL."""
        if domain is None:
            domains = ["example.com", "test.org", "sample.net", "demo.io"]
            domain = random.choice(domains)
        
        if path is None:
            paths = ["/", "/api/v1", "/resources", "/items", "/data"]
            path = random.choice(paths)
        
        url = f"{scheme}://{domain}{path}"
        
        if query_params:
            query_string = "&".join([f"{k}={v}" for k, v in query_params.items()])
            url += f"?{query_string}"
        
        return url
    
    def generate_phone(self, country_code: str = "+1", format: str = "xxx-xxx-xxxx") -> str:
        """Generate a random phone number."""
        if format == "xxx-xxx-xxxx":
            number = ''.join(random.choice(string.digits) for _ in range(10))
            formatted = f"{number[:3]}-{number[3:6]}-{number[6:]}"
        elif format == "(xxx) xxx-xxxx":
            number = ''.join(random.choice(string.digits) for _ in range(10))
            formatted = f"({number[:3]}) {number[3:6]}-{number[6:]}"
        else:
            # Default to a simple format
            number = ''.join(random.choice(string.digits) for _ in range(10))
            formatted = number
        
        return f"{country_code} {formatted}"
    
    def generate_edge_cases(self, data_type: str) -> List[Any]:
        """Generate edge case values for a given data type."""
        if data_type.lower() in ["str", "string"]:
            return [
                "",  # Empty string
                " ",  # Space
                "\n",  # Newline
                "\t",  # Tab
                "a" * 1000,  # Very long string
                "😀",  # Unicode emoji
                "null",  # String that looks like null
                "undefined",  # String that looks like undefined
            ]
        elif data_type.lower() in ["int", "integer"]:
            return [
                0,  # Zero
                -1,  # Negative
                1,  # Positive
                2**31 - 1,  # Max 32-bit int
                -2**31,  # Min 32-bit int
                2**63 - 1,  # Max 64-bit int
                -2**63,  # Min 64-bit int
            ]
        elif data_type.lower() in ["float", "double", "decimal"]:
            return [
                0.0,  # Zero
                -0.0,  # Negative zero
                1.0,  # One
                -1.0,  # Negative one
                3.14159,  # Pi
                float('inf'),  # Infinity
                float('-inf'),  # Negative infinity
                0.1 + 0.2,  # Floating point precision issue
            ]
        elif data_type.lower() in ["bool", "boolean"]:
            return [
                True,  # True
                False,  # False
            ]
        elif data_type.lower() in ["list", "array"]:
            return [
                [],  # Empty list
                [None],  # List with None
                [1, 2, 3, 4, 5],  # Typical list
                [1] * 1000,  # Large list
                ["a", "b", "c", "a", "b"],  # List with duplicates
            ]
        elif data_type.lower() in ["dict", "object", "map"]:
            return [
                {},  # Empty dict
                {"key": None},  # Dict with None value
                {"a": 1, "b": 2, "c": 3},  # Typical dict
                {f"key_{i}": i for i in range(100)},  # Large dict
            ]
        else:
            return [None]  # Default edge case