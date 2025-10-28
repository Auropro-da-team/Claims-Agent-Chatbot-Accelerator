import yaml
from pathlib import Path
import logging

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
REGISTRY_PATH = Path(__file__).parent.parent.parent / "prompt_registry.yaml"

def load_prompts(accelerator_name: str = "insurance_claim_assistant") -> dict:
    try:
        with open(REGISTRY_PATH, 'r') as f:
            registry = yaml.safe_load(f)
        version = registry['prompts_registry'][accelerator_name]['current_version']
        prompt_file = PROMPTS_DIR / f"{accelerator_name}_{version}.yaml"
        with open(prompt_file, 'r') as f:
            prompts_config = yaml.safe_load(f)
        logging.info(f"Successfully loaded prompts for '{accelerator_name}' version '{version}'")
        return prompts_config.get('prompts', {})
    except Exception as e:
        logging.error(f"CRITICAL ERROR: Could not load prompts. Check registry and YAML files. Error: {e}")
        return {}

prompts = load_prompts()

def get_prompt(prompt_key: str, **kwargs) -> str:
    if not prompts or prompt_key not in prompts:
        error_msg = f"Prompt key '{prompt_key}' not found. Ensure it exists in the YAML file."
        logging.error(error_msg)
        return error_msg
    
    return prompts[prompt_key]['instructions'].format(**kwargs)