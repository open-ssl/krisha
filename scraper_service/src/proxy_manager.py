import logging
import time
from typing import Optional

from fp.fp import FreeProxy


class ProxyManager:
    """Manager for handling proxy addresses"""

    def __init__(self):
        self.timeout = 2

    def get_proxy(self) -> Optional[dict]:
        """
        Get new proxy address for each request

        Returns:
            Optional[dict]: Proxy configuration for requests or None if no proxy available
        """
        start_time = time.time()
        logging.info("Getting new proxy...")

        try:
            # Получаем новый прокси для каждого запроса
            proxy = FreeProxy(timeout=self.timeout, rand=True, anonym=True).get()

            if proxy:
                proxy_config = {"http": proxy, "https": proxy}
                get_time = time.time() - start_time
                logging.info(f"Got new proxy: {proxy} (took {get_time:.2f}s)")
                return proxy_config
            else:
                logging.warning("No working proxy found")
                return None

        except Exception as e:
            logging.error(f"Error getting proxy: {e}")
            return None
