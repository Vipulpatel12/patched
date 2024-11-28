import json

from requests import request

from patchwork.step import Step


class CallAPI(Step):
    def __init__(self, inputs):
        """Initializes an instance of the class with the provided inputs.
        
        Args:
            inputs dict: A dictionary containing initialization parameters:
                - url (str): The URL for the request.
                - method (str): The HTTP method for the request (e.g., GET, POST).
                - headers (dict or str, optional): A dictionary of headers for the request or a JSON string representing headers.
                - body (dict, optional): A dictionary that will be converted to a JSON string as the body of the request.
        
        Returns:
            None: The constructor does not return any value.
        """
        super().__init__(inputs)
        self.url = inputs["url"]
        self.method = inputs["method"]
        possible_headers = inputs.get("headers", {})
        if not isinstance(possible_headers, dict):
            possible_headers = json.loads(possible_headers)
        self.headers = possible_headers
        self.body = inputs.get("body")
        if self.body and isinstance(self.body, dict):
            self.body = json.dumps(self.body)

    def run(self):
        """Executes an HTTP request using the specified method and URL, and returns the response details.
        
        Args:
            self: Object instance of the class where the method resides.
        
        Returns:
            dict: A dictionary containing the response status code, headers, and body text.
        """ 
        res = request(self.method, self.url, headers=self.headers, data=self.body)
        return dict(status_code=res.status_code, headers=res.headers, body=res.text)
