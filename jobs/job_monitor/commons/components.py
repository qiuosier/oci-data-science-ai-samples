import os
import traceback
import uuid

import oci


from flask import Flask, request

from commons import service
from commons.auth import (
    get_authentication,
    get_tenancy_ocid,
)
from commons.logs import logger
from commons.config import get_config, get_endpoint
from commons.validation import check_compartment_project


# Flask templates location
app = Flask(
    __name__, template_folder=os.path.join(os.path.dirname(__file__), "templates")
)
# Use hardware address as secret key so it will likely be unique for each computer.
app.secret_key = str(uuid.getnode())


def get_compartments():
    """Gets the compartments in the tenancy."""
    auth = get_authentication()
    tenancy_ocid = get_tenancy_ocid(auth)
    logger.debug("Tenancy ID: %s", tenancy_ocid)
    client = oci.identity.IdentityClient(**auth)
    compartments = []
    error = None
    # User may not have permissions to list compartment.
    try:
        compartments.extend(
            service.list_all_sub_compartments(client, compartment_id=tenancy_ocid)
        )
    except oci.exceptions.ServiceError:
        traceback.print_exc()
        error = f"ERROR: Unable to list all sub compartment in tenancy {tenancy_ocid}."
        try:
            compartments.append(
                service.list_all_child_compartments(client, compartment_id=tenancy_ocid)
            )
        except oci.exceptions.ServiceError:
            traceback.print_exc()
            error = f"ERROR: Unable to list all child compartment in tenancy {tenancy_ocid}."
    try:
        root_compartment = client.get_compartment(tenancy_ocid).data
        compartments.insert(0, root_compartment)
    except oci.exceptions.ServiceError:
        traceback.print_exc()
        error = f"ERROR: Unable to get details of the root compartment {tenancy_ocid}."
        if compartments:
            compartments.insert(
                0,
                oci.identity.models.Compartment(
                    id=tenancy_ocid, name=" ** Root - Name N/A **"
                ),
            )
    return {"compartments": compartments, "error": error}


def base_context():
    """Load compartments, project_id, limit and endpoint."""
    compartment_id = request.args.get("c")
    project_id = request.args.get("p")
    limit = request.args.get("limit", 10)

    config = get_config()
    endpoint = get_endpoint()

    if project_id:
        compartment_id, project_id = check_compartment_project(
            compartment_id, project_id
        )
    else:
        compartment_id = None

    context = dict(
        compartment_id=compartment_id,
        project_id=project_id,
        limit=limit,
        service_endpoint=endpoint,
        config=config,
    )
    return context

def base_context_with_compartments():
    context = base_context()
    context.update(get_compartments())
    return context
