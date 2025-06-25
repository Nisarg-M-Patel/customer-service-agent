"""Mock data provider for testing and development."""

from typing import List, Dict, Optional
from datetime import datetime
from ...database.models import StandardProduct, StandardCustomer

class MockProvider:
    """Provides mock data in standard format."""
    
    def __init__(self):
        self.products = self._generate_mock_products()
        self.customers = self._generate_mock_customers()
    
    def search_products(self, query: str = None, category: str = None, **filters) -> List[StandardProduct]:
        """Search mock products."""
        results = self.products.copy()
        
        if query:
            query_lower = query.lower()
            results = [
                p for p in results 
                if query_lower in p.title.lower() 
                or query_lower in p.description.lower()
                or any(query_lower in tag.lower() for tag in p.tags)
            ]
        
        if category:
            results = [p for p in results if category.lower() in [c.lower() for c in p.categories]]
        
        return results[:10]  # Limit results
    
    def get_product_by_id(self, product_id: str) -> Optional[StandardProduct]:
        """Get specific product by ID."""
        for product in self.products:
            if product.id == product_id:
                return product
        return None
    
    def check_inventory(self, product_id: str) -> Dict:
        """Check product inventory."""
        product = self.get_product_by_id(product_id)
        if not product:
            return {"available": False, "error": "Product not found"}
        
        return {
            "available": product.inventory_quantity > 0,
            "quantity": product.inventory_quantity,
            "product_name": product.title
        }
    
    def get_customer_by_id(self, customer_id: str) -> Optional[StandardCustomer]:
        """Get customer by ID."""
        for customer in self.customers:
            if customer.id == customer_id:
                return customer
        return None
    
    def _generate_mock_products(self) -> List[StandardProduct]:
        """Generate mock product data."""
        now = datetime.now()
        
        return [
            StandardProduct(
                id="mock-001",
                title="Premium Potting Soil",
                description="High-quality potting soil perfect for indoor and outdoor plants.",
                price=24.99,
                compare_at_price=29.99,
                sku="SOIL-001",
                inventory_quantity=50,
                tags=["soil", "gardening", "indoor", "outdoor"],
                categories=["Soil & Amendments"],
                images=["https://example.com/soil1.jpg"],
                created_at=now,
                updated_at=now
            ),
            StandardProduct(
                id="mock-002",
                title="Tomato Seeds - Heritage Variety",
                description="Heirloom tomato seeds, perfect for home gardens.",
                price=4.99,
                sku="SEED-TOM-001",
                inventory_quantity=100,
                tags=["seeds", "tomato", "vegetables", "heirloom"],
                categories=["Seeds", "Vegetables"],
                images=["https://example.com/tomato-seeds.jpg"],
                created_at=now,
                updated_at=now
            ),
            StandardProduct(
                id="mock-003",
                title="Garden Trowel - Stainless Steel",
                description="Durable stainless steel garden trowel with comfortable grip.",
                price=19.99,
                sku="TOOL-TROW-001",
                inventory_quantity=25,
                tags=["tools", "trowel", "stainless steel", "gardening"],
                categories=["Garden Tools"],
                images=["https://example.com/trowel.jpg"],
                created_at=now,
                updated_at=now
            ),
            StandardProduct(
                id="mock-004",
                title="Organic Fertilizer - All Purpose",
                description="Organic all-purpose fertilizer for healthy plant growth.",
                price=15.99,
                compare_at_price=18.99,
                sku="FERT-ORG-001",
                inventory_quantity=75,
                tags=["fertilizer", "organic", "all-purpose", "nutrients"],
                categories=["Fertilizers"],
                images=["https://example.com/fertilizer.jpg"],
                created_at=now,
                updated_at=now
            ),
            StandardProduct(
                id="mock-005",
                title="Petunia Plants - Mixed Colors",
                description="Beautiful petunia plants in assorted colors.",
                price=8.99,
                sku="PLANT-PET-001",
                inventory_quantity=30,
                tags=["plants", "petunia", "flowers", "annual"],
                categories=["Live Plants", "Flowers"],
                images=["https://example.com/petunias.jpg"],
                created_at=now,
                updated_at=now
            )
        ]
    
    def _generate_mock_customers(self) -> List[StandardCustomer]:
        """Generate mock customer data."""
        now = datetime.now()
        
        return [
            StandardCustomer(
                id="123",
                first_name="Alex",
                last_name="Johnson",
                email="alex.johnson@example.com",
                phone="+1-702-555-1212",
                purchase_history=[
                    {"date": "2023-03-05", "total": 35.98, "items": ["mock-001", "mock-003"]},
                    {"date": "2023-07-12", "total": 42.50, "items": ["mock-002", "mock-005"]}
                ],
                loyalty_points=133,
                preferences={
                    "garden_type": "backyard",
                    "garden_size": "medium",
                    "interests": ["flowers", "vegetables"]
                },
                created_at=now,
                updated_at=now
            )
        ]