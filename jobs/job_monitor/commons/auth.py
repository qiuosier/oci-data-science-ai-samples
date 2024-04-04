import os

import ads

import oci
import requests

from flask import request
from commons.logs import logger
from commons.config import CONFIG_MAP, CONST_OVERRIDE_TENANCY, get_endpoint, get_config

ENV_OCI_KEY_PROFILE = "OCI_KEY_PROFILE"


def instance_principal_available():
    """Checks if instance principal is available."""
    try:
        requests.get(
            oci.auth.signers.InstancePrincipalsSecurityTokenSigner.GET_REGION_URL,
            headers=oci.auth.signers.InstancePrincipalsDelegationTokenSigner.METADATA_AUTH_HEADERS,
            timeout=1,
        )
        return True
    except Exception:
        return False


def get_authentication(
    config_path=oci.config.DEFAULT_LOCATION,
    profile_name=None,
):
    """Returns a dictionary containing the authentication needed for initializing OCI client (e.g. DataScienceClient).
    This function checks if OCI API key config exists, if config exists, it will be loaded and used for authentication.
    If config does not exist, resource principal or instance principal will be used if available.
    To use a config at a non-default location, set the OCI_KEY_LOCATION environment variable.
    To use a non-default config profile, set the OCI_KEY_PROFILE_NAME environment variable.

    Returns
    -------
    dict
        A dictionary containing two keys: config and signer (optional).
        config is a dictionary containing api key authentication information.
        signer is an OCI Signer object for resource principal or instance principal authentication.
        IMPORTANT: signer will be returned only if config is not empty.

    Raises
    ------
    Exception
        When no authentication method is available.
    """

    if profile_name is None:
        profile_name = CONFIG_MAP.get_profile()
    if profile_name is None:
        profile_name = os.environ.get(ENV_OCI_KEY_PROFILE, oci.config.DEFAULT_PROFILE)

    if os.path.exists(os.path.expanduser(config_path)):
        logger.debug("Using OCI config: %s, profile: %s", config_path, profile_name)
        oci_config = oci.config.from_file(
            file_location=config_path, profile_name=profile_name
        )
        if "security_token_file" in oci_config and "key_file" in oci_config:
            try:
                token_file = oci_config["security_token_file"]
                with open(token_file, "r", encoding="utf-8") as f:
                    token = f.read()
                private_key = oci.signer.load_private_key_from_file(
                    oci_config["key_file"]
                )
                signer = oci.auth.signers.SecurityTokenSigner(token, private_key)
                oci_auth = {"config": oci_config, "signer": signer}
            except FileNotFoundError:
                oci_auth = {"config": oci_config}
        else:
            oci_auth = {"config": oci_config}
    elif (
        oci.auth.signers.resource_principals_signer.OCI_RESOURCE_PRINCIPAL_VERSION
        in os.environ
    ):
        oci_config = {}
        signer = oci.auth.signers.get_resource_principals_signer()
        oci_auth = dict(config=oci_config, signer=signer)
    elif instance_principal_available():
        oci_config = {}
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        oci_auth = dict(config=oci_config, signer=signer)
    else:
        raise EnvironmentError("Cannot determine authentication method.")
    # ads.set_auth(**oci_auth)

    return oci_auth


def get_ds_auth(profile=None, client="oci"):
    """Get the authentication and service endpoint."""
    auth = get_authentication(profile_name=profile)
    endpoint = get_endpoint(profile=profile)
    if endpoint:
        if client == "oci":
            auth["service_endpoint"] = endpoint
        else:
            auth["client_kwargs"] = {"service_endpoint": endpoint}
    return auth


def get_tenancy_ocid(auth=None):
    """Get tenancy OCID."""
    # Tenancy ID from GET parameters
    tenancy_id = request.args.get("t")
    if tenancy_id:
        return tenancy_id
    # Tenancy ID from custom config
    config = get_config()
    if config.get(CONST_OVERRIDE_TENANCY):
        return config[CONST_OVERRIDE_TENANCY]
    # Tenancy ID from OCI auth
    if not auth:
        auth = get_authentication()
    if auth["config"]:
        if "TENANCY_OCID" in os.environ:
            tenancy_id = os.environ["TENANCY_OCID"]
        elif "override_tenancy" in auth["config"]:
            tenancy_id = auth["config"]["override_tenancy"]
        else:
            tenancy_id = auth["config"]["tenancy"]
    else:
        tenancy_id = getattr(auth["signer"], "tenancy_id", None)
    return tenancy_id
