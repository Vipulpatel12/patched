from __future__ import annotations

import asyncio
import atexit
import contextlib
import platform
import socket
import sys
from importlib import metadata
from pathlib import Path
from threading import Thread
from typing import Any

import click
import requests
from git.repo.base import Repo
from requests import Response, Session
from requests.adapters import DEFAULT_POOLBLOCK, HTTPAdapter
from urllib3 import HTTPConnectionPool, HTTPSConnectionPool, PoolManager

from patchwork.common.utils.user_config import get_user_config
from patchwork.common.utils.utils import get_current_branch, is_container
from patchwork.logger import logger


class TCPKeepAliveHTTPSConnectionPool(HTTPSConnectionPool):
    # probe start
    TCP_KEEP_IDLE = 60
    # probe interval
    TCP_KEEPALIVE_INTERVAL = 60
    # probe times
    TCP_KEEP_CNT = 3

    def _validate_conn(self, conn):
        """Validates and configures the TCP connection settings based on the operating system.
        
        Args:
            conn Connection: The connection object that needs to be validated and configured.
        
        Returns:
            None: This method does not return any value.
        """
        super()._validate_conn(conn)

        if sys.platform == "linux":
            if hasattr(socket, "TCP_KEEPIDLE"):
                conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, self.TCP_KEEP_IDLE)
            if hasattr(socket, "TCP_KEEPINTVL"):
                conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self.TCP_KEEPALIVE_INTERVAL)
            if hasattr(socket, "TCP_KEEPCNT"):
                conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self.TCP_KEEP_CNT)
        elif sys.platform == "darwin":
            conn.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            conn.sock.setsockopt(socket.IPPROTO_TCP, 0x10, self.TCP_KEEPALIVE_INTERVAL)
        elif sys.platform == "win32":
            conn.sock.ioctl(
                socket.SIO_KEEPALIVE_VALS, (1, self.TCP_KEEP_IDLE * 1000, self.TCP_KEEPALIVE_INTERVAL * 1000)
            )


class KeepAlivePoolManager(PoolManager):
    def __init__(self, num_pools=10, headers=None, **connection_pool_kw):
        """Initializes a new instance of the class, setting up connection pooling for HTTP and HTTPS.
        
        Args:
            num_pools (int): The number of connection pools to create. Defaults to 10.
            headers (dict, optional): Custom headers to include with the connection requests. Defaults to None.
            **connection_pool_kw: Additional keyword arguments for connection pool configuration.
        
        Returns:
            None
        """
        super().__init__(num_pools=num_pools, headers=headers, **connection_pool_kw)
        self.pool_classes_by_scheme = {
            "http": HTTPConnectionPool,
            "https": TCPKeepAliveHTTPSConnectionPool,
        }


class KeepAliveHTTPSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=DEFAULT_POOLBLOCK, **pool_kwargs):
        """Initializes a pool manager with specified connection settings.
        
        Args:
            connections int: The number of connection pools to create.
            maxsize int: The maximum number of connections to save in the pool.
            block bool, optional: Whether to block when no connections are available (default is DEFAULT_POOLBLOCK).
            **pool_kwargs: Additional keyword arguments to pass to the pool manager.
        
        Returns:
            None: This method does not return a value.
        """
        self.poolmanager = KeepAlivePoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            strict=True,
            **pool_kwargs,
        )


class PatchedClient(click.ParamType):
    TOKEN_URL = "https://app.patched.codes/signin"
    DEFAULT_PATCH_URL = "https://patchwork.patched.codes"
    ALLOWED_TELEMETRY_KEYS = {
        "model",
    }

    def __init__(self, access_token: str, url: str = DEFAULT_PATCH_URL):
        """Initializes an instance of the class with an access token and an optional URL.
        
        Args:
            access_token str: The access token required for authentication.
            url str: (Optional) The URL to be used for API requests, defaulting to DEFAULT_PATCH_URL.
        
        Returns:
            None
        """
        self.access_token = access_token
        self.url = url
        self._session = Session()
        atexit.register(self._session.close)
        self._edit_tcp_alive()

    def _edit_tcp_alive(self):
        # credits to https://www.finbourne.com/blog/the-mysterious-hanging-client-tcp-keep-alives
        """Configures the session to use TCP keep-alive by mounting a KeepAliveHTTPSAdapter.
        
        This method is intended to enhance the persistence of the session by maintaining
        TCP connections alive for longer periods, potentially improving performance for
        subsequent requests.
        
        Args:
            None
        
        Returns:
            None
        """
        self._session.mount("https://", KeepAliveHTTPSAdapter())

    def _post(self, **kwargs) -> Response | None:
        """Sends a POST request using the session.
        
        Args:
            **kwargs: Additional keyword arguments that will be passed to the POST request.
        
        Returns:
            Response | None: Returns the response from the POST request if successful, otherwise None.
        """
        try:
            response = self._session.post(**kwargs)
        except requests.ConnectionError as e:
            logger.error(f"Unable to establish connection to patched server: {e}")
            return None
        except requests.RequestException as e:
            logger.error(f"Request failed with exception: {e}")
            return None

        return response

    def _get(self, **kwargs) -> Response | None:
        """Executes a GET request using the session and handles any potential exceptions.
        
        Args:
            **kwargs: Additional keyword arguments that are passed to the session's get method.
        
        Returns:
            Response | None: The Response object if the request is successful, None if there was a connection error or another request exception.
        """
        try:
            response = self._session.get(**kwargs)
        except requests.ConnectionError as e:
            logger.error(f"Unable to establish connection to patched server: {e}")
            return None
        except requests.RequestException as e:
            logger.error(f"Request failed with exception: {e}")
            return None

        return response

    def test_token(self) -> bool:
        """Tests the validity of the access token by sending a request to the token test endpoint.
        
        This method sends a POST request to the specified token test URL with the current access token. 
        It evaluates the response to determine if the token is valid or not, logging any errors encountered.
        
        Returns:
            bool: True if the access token is valid and the response indicates a successful test, 
                  False otherwise.
        """
        response = self._post(
            url=self.url + "/token/test", headers={"Authorization": f"Bearer {self.access_token}"}, json={}
        )

        if response is None:
            return False

        if not response.ok:
            logger.error(f"Access Token failed with status code {response.status_code}")
            return False

        body = response.json()
        if "msg" not in body:
            logger.error("Access Token test failed with unknown response")
            return False

        return body["msg"] == "ok"

    def __handle_telemetry_inputs(self, inputs: dict[str, Any]) -> dict:
        """Handles telemetry inputs by filtering and modifying keys based on allowed telemetry keys.
        
        Args:
            inputs dict[str, Any]: A dictionary containing telemetry inputs where keys are strings and values can be of any type.
        
        Returns:
            dict: A modified dictionary with additional keys set to True for any keys not in the allowed telemetry keys.
        """
        diff_keys = set(inputs.keys()).difference(self.ALLOWED_TELEMETRY_KEYS)

        inputs_copy = inputs.copy()
        for key in diff_keys:
            inputs_copy[key] = True

        return inputs_copy

    async def _public_telemetry(self, patchflow: str, inputs: dict[str, Any]):
        """Sends telemetry data to a remote server.
        
        Args:
            patchflow str: The identifier for the patch flow being used.
            inputs dict[str, Any]: A dictionary containing input parameters related to the telemetry.
        
        Returns:
            None: This method does not return any value.
        """
        user_config = get_user_config()
        requests.post(
            url=self.url + "/v1/telemetry/",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json=dict(
                client_id=user_config.id,
                patchflow=patchflow,
                inputs=self.__handle_telemetry_inputs(inputs),
                environment=dict(
                    system=platform.system(),
                    release=platform.release(),
                    machine=platform.machine(),
                    python_version=platform.python_version(),
                    cli_version=metadata.version("patchwork-cli"),
                    is_container=is_container(),
                ),
            ),
        )

    def send_public_telemetry(self, patchflow: str, inputs: dict):
        """Starts a new thread to send public telemetry data asynchronously.
        
        Args:
            patchflow str: A string identifier for the telemetry patch flow.
            inputs dict: A dictionary containing the inputs required for the telemetry.
        
        Returns:
            None: This method does not return any value.
        """
        try:
            _thread = Thread(target=asyncio.run, args=(self._public_telemetry(patchflow, inputs),))
            _thread.start()
        except Exception as e:
            logger.debug(f"Failed to send public telemetry: {e}")

    @contextlib.contextmanager
    def patched_telemetry(self, patchflow: str, inputs: dict):
        """Handles the telemetry of a patchflow run, yielding control between operations.
        
        This method verifies the access token, tests its validity, records the patchflow run, 
        and ensures the run is finished correctly, logging any errors encountered during the process.
        
        Args:
            patchflow (str): The identifier for the patchflow being recorded.
            inputs (dict): A dictionary containing inputs relevant to the patchflow telemetry.
        
        Returns:
            generator: Yields control at various stages of the process, allowing for async handling.
        """
        if not self.access_token:
            yield
            return

        try:
            is_valid_client = self.test_token()
        except Exception as e:
            logger.error(f"Access Token test failed: {e}")
            yield
            return

        if not is_valid_client:
            yield
            return

        try:
            repo = Repo(Path.cwd(), search_parent_directories=True)
            patchflow_run_id = self.record_patchflow_run(patchflow, repo, self.__handle_telemetry_inputs(inputs))
        except Exception as e:
            logger.error(f"Failed to record patchflow run: {e}")
            yield
            return

        if patchflow_run_id is None:
            yield
            return

        try:
            yield
        finally:
            try:
                self.finish_record_patchflow_run(patchflow_run_id, patchflow, repo)
            except Exception as e:
                logger.error(f"Failed to finish patchflow run: {e}")

    def record_patchflow_run(self, patchflow: str, repo: Repo, inputs: dict) -> int | None:
        """Records a Patchflow run for a given repository and inputs.
        
        Args:
            patchflow str: The identifier for the patchflow being recorded.
            repo Repo: The repository instance where the patchflow is applied.
            inputs dict: A dictionary of inputs required for the patchflow run.
        
        Returns:
            int | None: The ID of the recorded patchflow run if successful, otherwise None.
        """
        head = get_current_branch(repo)
        branch = head.remote_head if head.is_remote() else head.name

        response = self._post(
            url=self.url + "/v1/patchwork/",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={"url": repo.remotes.origin.url, "patchflow": patchflow, "branch": branch, "inputs": inputs},
        )

        if response is None:
            return None

        if not response.ok:
            logger.error(f"Failed to record patchflow run with status code {response.status_code}, msg:{response.text}")
            return None

        logger.debug(f"Patchflow run recorded for {patchflow}")
        return response.json()["id"]

    def finish_record_patchflow_run(self, id: int, patchflow: str, repo: Repo) -> None:
        """Finishes a Patchflow run by sending a POST request to the Patchwork API.
        
        Args:
            id int: The identifier of the Patchflow run to be finished.
            patchflow str: The name or identifier of the patchflow being applied.
            repo Repo: The repository object containing information about the repository, particularly the remote URL.
        
        Returns:
            None: This method does not return a value; it performs a side effect by sending a request and logging the outcome.
        """
        response = self._post(
            url=self.url + "/v1/patchwork/",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={
                "id": id,
                "url": repo.remotes.origin.url,
                "patchflow": patchflow,
            },
        )

        if response is None:
            return

        if not response.ok:
            logger.error(f"Failed to finish patchflow run with status code {response.status_code}, msg:{response.text}")
            return

        logger.debug(f"Patchflow run finished for {id}")
