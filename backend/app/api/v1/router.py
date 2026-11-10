from fastapi import APIRouter

from app.api.v1 import auth, orders, products

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(orders.router)
api_router.include_router(products.router)
