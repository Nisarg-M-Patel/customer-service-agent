import subprocess
import json
import logging

logger = logging.getLogger(__name__)

async def provision_customer_services(business_id: str, provider: str, shop_url: str, access_token: str) -> dict:
    """Deploy customer-specific services"""
    
    tf_vars = [
        f"-var=business_id={business_id}",
        f"-var=ecommerce_provider={provider}",  # Changed variable name
        f"-var=shop_url={shop_url}",
        f"-var=access_token={access_token}"
    ]
    
    terraform_dir = "./terraform"
    
    try:
        logger.info(f"Provisioning {business_id}")
        
        subprocess.run(["terraform", "init"], cwd=terraform_dir, check=True)
        subprocess.run(["terraform", "apply", "-auto-approve"] + tf_vars, cwd=terraform_dir, check=True)
        
        result = subprocess.run(["terraform", "output", "-json"], cwd=terraform_dir, capture_output=True, text=True, check=True)
        outputs = json.loads(result.stdout)
        
        return {
            "admin_api_url": outputs["admin_api_url"]["value"],
            "agent_url": outputs["agent_url"]["value"]
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Terraform failed: {e}")
        raise Exception(f"Provisioning failed: {e}")