from typing import Any, Dict


def check_with_endpoint(config: Dict[str, Any]) -> Dict[str, Any]:
    raise RuntimeError(
        "Endpoint checker not configured. Use target.mode=playwright or add endpoint settings."
    )
