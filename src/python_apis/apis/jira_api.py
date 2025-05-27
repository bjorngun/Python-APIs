"""This module contains the functionality concerning the
connection and the methods that gets data from AD and can modify the AD.

This module was build as an "in the same domain" AD connection and has no plans
to extend to being able to connect through a custom user and password. Hence
this package will need a user that has the required permissions to edit/read the
AD to run it effectively.
"""

from typing import Any
from logging import getLogger
from requests.auth import HTTPBasicAuth
import requests


class JiraServerError(Exception):
    """Raised when the Jira server returns a 500 error."""


class JiraUnknownError(Exception):
    """Raised when an unknown error is returned from Jira."""


class SpecificJiraError(Exception):
    """Raised for Jira errors that have a known error string."""


class JiraConnection:  # pylint: disable=too-few-public-methods
    """This class contains the functionality concerning the
    connection and the methods that gets data from AD and can modify the AD.
    """

    def __init__(self, endpoint: str, token: str, user):
        """Initializes the class, generating headers then getting the
        neccicery authentication info as parameters.  The source of the
        parameters are most likely from the env file.
        
        The reason why we don't get the env files here instead is so that we
        can initiate multiple instances of any specific connection with
        difference connection data for example with a different user.

        Instance Variables
            endpoint:           String containing the value of the base url
            token:              String containing the Bearer token
            headers:            String containing email
        """
        self.logger = getLogger(__name__)

        self.default_endpoint = endpoint
        self.auth = HTTPBasicAuth(user, token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-ExperimentalApi": "opt-in",
        }

    def get_objects(
        self, url_suffix: str,
        parameters: dict[str, Any] = None,
        endpoint: str = None
        ) -> dict[str, dict]:
        """
        Args:
            url_suffix (str): Specific end of the url to point to the right url
            parameters (dict[str, Any]): A dictionary of pairs of parameters
                in the form of {parameter_name: parameter_value}

        Returns:
            dict[str, dict]
        """
        if endpoint is None:
            endpoint = self.default_endpoint
        url = f"{endpoint}{url_suffix}"
        response = requests.get(
            url,
            headers=self.headers,
            params=parameters,
            auth=self.auth,
            timeout=60,
        )
        # response = requests.get(
            # url=url, params=parameters, headers=self.headers, auth=self.basic_auth)
        response.encoding = "utf-8"

        # status code 200 means successful get
        if response.status_code == 200:
            results = response.json() #This will change for many solutions
            self.logger.info(
                "Successfully got objects for %s%s, count: {len(results)}",
                endpoint,
                url_suffix
            )
            return results
        exception_str = (
            f'Status code {response.status_code} when creating '
            f'{url_suffix}: parameters: {parameters}, with url: {url} and with '
            f'the following response: {response.text}'
        )
        # 500, server error, and it has a different format than other responses
        if response.status_code == 500:
            self.logger.error(exception_str)
            raise JiraServerError(exception_str)
        if "Some endpoint specific string" in response.text:
            raise SpecificJiraError(f'parameters: {parameters}')
        raise JiraUnknownError(exception_str)
