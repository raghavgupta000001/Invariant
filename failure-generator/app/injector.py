import httpx
import structlog
from typing import Optional, Any
from app.config import SIMULATOR_URL, ORDER_URL, PAYMENT_URL, ERP_URL, SHIPPING_URL
from catalog.scenarios import FailureScenario, get_scenario

logger = structlog.get_logger()


class FailureInjector:
    def __init__(self):
        self.simulator_url = SIMULATOR_URL
        self.service_urls = {
            "order": ORDER_URL,
            "payment": PAYMENT_URL,
            "erp": ERP_URL,
            "shipping": SHIPPING_URL,
        }

    async def reset_all_services(self) -> dict[str, bool]:
        """Resets failure flags across all services."""
        results = {}
        async with httpx.AsyncClient(timeout=5.0) as client:
            # ERP failure reset
            try:
                res = await client.post(f"{self.service_urls['erp']}/erp/failure", params={"mode": "erp_silent_failure", "active": "false"})
                results["erp"] = res.status_code == 200
            except Exception as e:
                logger.warning("failed_to_reset_erp", error=str(e))
                results["erp"] = False

            # Shipping failure reset
            try:
                res = await client.post(f"{self.service_urls['shipping']}/shipments/failure", params={"mode": "shipment_creation_fails", "active": "false"})
                results["shipping"] = res.status_code == 200
            except Exception as e:
                logger.warning("failed_to_reset_shipping", error=str(e))
                results["shipping"] = False

        return results

    async def execute_scenario(self, scenario: FailureScenario) -> dict[str, Any]:
        """
        Executes a failure scenario through the simulator and records observed execution.
        """
        log = logger.bind(scenario_id=scenario.id, scenario_name=scenario.name)
        log.info("executing_scenario")

        payload = {
            "customer_email": f"test_{scenario.id.lower()}@example.com",
            "customer_name": f"Test Customer {scenario.id}",
            "sku": "LAPTOP-PRO-15",
            "product_name": "Professional Laptop 15\"",
            "qty": 1,
            "unit_price_paise": 6_000_000,
            **scenario.simulate_params,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(f"{self.simulator_url}/simulate/happy_path", json=payload)
                if resp.status_code in (200, 201):
                    sim_result = resp.json()
                    status = sim_result.get("final_status")
                    transaction_ref = sim_result.get("transaction_ref")
                else:
                    sim_result = {"error": resp.text, "status_code": resp.status_code}
                    status = "ERROR"
                    transaction_ref = None
            except Exception as e:
                sim_result = {"error": str(e)}
                status = "NETWORK_ERROR"
                transaction_ref = None

        # Verify cross-system state
        observed_consistency = None
        if transaction_ref:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    status_resp = await client.get(f"{self.simulator_url}/simulate/status/{transaction_ref}")
                    if status_resp.status_code == 200:
                        observed_consistency = status_resp.json()
            except Exception:
                pass

        return {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "category": scenario.category,
            "severity": scenario.severity,
            "ground_truth": scenario.ground_truth.__dict__,
            "simulation_result": sim_result,
            "status": status,
            "transaction_ref": transaction_ref,
            "observed_consistency": observed_consistency,
        }

