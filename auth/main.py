import os
import re
import httpx
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from terraform_runner import provision_customer_services

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Customer Service Auth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def shop_to_business_id(shop_domain: str) -> str:
    """Convert shop.myshopify.com to shop_myshopify_com"""
    return re.sub(r'[^a-zA-Z0-9]', '_', shop_domain.lower().replace('.myshopify.com', ''))

async def exchange_shopify_code_for_token(code: str, shop: str, client_id: str, client_secret: str) -> str:
    """Exchange OAuth code for access token using provided app credentials"""
    token_url = f"https://{shop}.myshopify.com/admin/oauth/access_token"
    
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, json=payload)
        
    if response.status_code != 200:
        raise HTTPException(400, f"Failed to exchange code: {response.text}")
    
    return response.json()["access_token"]

async def warmup_customer_system(admin_api_url: str) -> bool:
    """Call the system warmup endpoint"""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(f"{admin_api_url}/api/system-warmup")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Warmup failed: {e}")
        return False

@app.get("/")
async def root():
    return {"service": "customer-service-auth", "status": "running"}

@app.get("/shopify/install")
async def shopify_install(shop: str, client_id: str):
    """Initiate Shopify OAuth flow - client_id comes from the app installation"""
    shop = shop.replace('.myshopify.com', '') + '.myshopify.com'
    
    oauth_url = f"https://{shop}/admin/oauth/authorize"
    params = {
        "client_id": client_id,
        "scope": "read_products,read_orders,read_customers",
        "redirect_uri": f"{os.getenv('AUTH_URL')}/shopify/callback",
        "state": f"shopify:{shop}:{client_id}"  # Include client_id in state
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    redirect_url = f"{oauth_url}?{query_string}"
    
    return RedirectResponse(redirect_url)

@app.get("/shopify/callback")
async def shopify_callback(
    code: str, 
    shop: str, 
    state: str,
    client_secret: str,  # App provides this
    background_tasks: BackgroundTasks
):
    """Handle OAuth callback - app credentials come from the request"""
    
    if not state.startswith("shopify:"):
        raise HTTPException(400, "Invalid state")
    
    # Extract client_id from state
    try:
        _, shop_from_state, client_id = state.split(":")
    except ValueError:
        raise HTTPException(400, "Invalid state format")
    
    access_token = await exchange_shopify_code_for_token(code, shop, client_id, client_secret)
    business_id = shop_to_business_id(shop)
    
    # Start provisioning in background
    background_tasks.add_task(provision_and_warmup, business_id, shop, access_token)
    
    return {
        "status": "success",
        "message": "Infrastructure provisioning started",
        "business_id": business_id
    }

async def provision_and_warmup(business_id: str, shop: str, access_token: str):
    """Background task to provision and warm up"""
    try:
        services = await provision_customer_services(
            business_id=business_id,
            provider="shopify",
            shop_url=shop,
            access_token=access_token
        )
        
        await warmup_customer_system(services["admin_api_url"])
        logger.info(f"Successfully set up customer {business_id}")
        
    except Exception as e:
        logger.error(f"Setup failed for {business_id}: {e}")

@app.post("/manual/provision")
async def manual_provision(business_id: str, provider: str, shop_url: str, access_token: str):
    """Manual provisioning for testing"""
    try:
        services = await provision_customer_services(business_id, provider, shop_url, access_token)
        return {"status": "success", "services": services}
    except Exception as e:
        raise HTTPException(500, f"Provisioning failed: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)