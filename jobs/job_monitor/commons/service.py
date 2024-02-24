import functools
import multiprocessing
import os
import traceback

import oci
from commons.config import get_config, CONST_SERVICE_ENDPOINT
from commons.errors import abort_with_json_error


ENV_OCI_ODSC_SERVICE_ENDPOINT = "OCI_ODSC_SERVICE_ENDPOINT"


def list_all_sub_compartments(client: oci.identity.IdentityClient, compartment_id):
    compartments = oci.pagination.list_call_get_all_results(
        client.list_compartments,
        compartment_id=compartment_id,
        compartment_id_in_subtree=True,
        access_level="ANY",
    ).data
    return compartments


def list_all_child_compartments(client: oci.identity.IdentityClient, compartment_id):
    compartments = oci.pagination.list_call_get_all_results(
        client.list_compartments,
        compartment_id=compartment_id,
    ).data
    return compartments


def with_service_endpoint(func):
    """Decorator for running ADS code with service endpoint in subprocess."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        config = get_config()
        if config.get(CONST_SERVICE_ENDPOINT):
            q = multiprocessing.Queue()

            # Set service endpoint env var and run function in subprocess
            def subprocess_func(q):
                os.environ[ENV_OCI_ODSC_SERVICE_ENDPOINT] = config.get(
                    CONST_SERVICE_ENDPOINT
                )
                try:
                    r = func(*args, **kwargs)
                    q.put(r)
                except Exception as ex:
                    traceback.print_exc()
                    q.put(str(ex))

            p = multiprocessing.Process(
                target=subprocess_func, args=args, kwargs=kwargs
            )
            p.start()
            p.join()
            if p.exitcode == 0:
                return q.get()
            abort_with_json_error(code=500, message=q.get())
        else:
            return func(*args, **kwargs)

    return wrapper


def get_endpoint():
    """Gets the service endpoint from config."""
    return get_config().get(CONST_SERVICE_ENDPOINT)
