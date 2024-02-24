import os

import ads
import configparser
import oci
import requests

from flask import request
from commons.logs import logger

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
        profile_name = request.args.get("profile")
    if profile_name is None:
        profile_name = os.environ.get(ENV_OCI_KEY_PROFILE, oci.config.DEFAULT_PROFILE)

    if os.path.exists(os.path.expanduser(config_path)):
        logger.info("Using OCI config: %s", config_path)
        logger.info("Using OCI profile: %s", profile_name)
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
    ads.set_auth(**oci_auth)
    return oci_auth


def load_oci_config(
    config_path=oci.config.DEFAULT_LOCATION,
    profile_name=os.environ.get(ENV_OCI_KEY_PROFILE, oci.config.DEFAULT_PROFILE),
):
    """Loads OCI config if exists, otherwise return empty dictionary."""
    if not os.path.exists(os.path.expanduser(config_path)):
        return {}
    oci_config = oci.config.from_file(
        file_location=config_path, profile_name=profile_name
    )
    return oci_config


def load_profiles(file_location=oci.config.DEFAULT_LOCATION):
    expanded_file_location = oci.config._get_config_path_with_fallback(file_location)

    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(expanded_file_location):
        raise oci.exceptions.ConfigFileNotFound(
            f"Could not find config file at {expanded_file_location}, "
            "please follow the instructions in the link to setup the config file "
            "https://docs.cloud.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm"
        )
    return {key: dict(parser[key]) for key in parser.keys()}
