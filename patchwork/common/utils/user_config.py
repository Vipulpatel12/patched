from __future__ import annotations

import functools
import hashlib
import uuid

from pydantic import BaseModel

from patchwork.logger import logger
from patchwork.managed_files import CONFIG_FILE


class __UserConfig(BaseModel):
    id: str = hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()

    def persist(self):
        """Persist the current model's state to a configuration file.
        
        Attempts to write the JSON representation of the model to a specified configuration file.
        If the operation fails, it logs the error message for debugging purposes.
        
        Args:
            self: The instance of the class containing the model to be persisted.
        
        Returns:
            None: This method does not return a value.
        """
        try:
            CONFIG_FILE.write_text(self.model_dump_json())
        except Exception as e:
            logger.debug(f"Failed to persist user config: {e}")


@functools.lru_cache(maxsize=None)
def get_user_config():
    """Retrieves the user configuration from a JSON file. If reading the configuration fails, a new user configuration is created and persisted.
    
    Args:
        None
    
    Returns:
        __UserConfig: An instance of the user configuration, either loaded from the JSON file or newly created.
    """
    try:
        return __UserConfig.model_validate_json(CONFIG_FILE.read_text())
    except Exception as e:
        logger.debug(f"Failed to read user config: {e}")

    user_config = __UserConfig()
    user_config.persist()
    return user_config
