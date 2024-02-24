import re
from flask import request
from ads.common.oci_resource import OCIResource
from commons.errors import abort_with_json_error


def check_ocid(ocid):
    if not re.match(r"ocid[0-9].[a-z]+.oc[0-9].[a-z-]+.[a-z0-9]+", ocid):
        abort_with_json_error(404, f"Invalid OCID: {ocid}")


def check_project_id(project_id):
    if not re.match(
        r"ocid[0-9].datascienceproject.oc[0-9].[a-z-]+.[a-z0-9]+", project_id
    ):
        abort_with_json_error(404, f"Invalid Project OCID: {project_id}")


def check_compartment_id(compartment_id):
    if not re.match(
        r"ocid[0-9].(compartment|tenancy).oc[0-9]..[a-z0-9]+", compartment_id
    ):
        abort_with_json_error(404, f"Invalid Compartment OCID: {compartment_id}")


def check_compartment_project(compartment_id, project_id):
    if str(project_id).lower() == "all":
        project_id = None
    else:
        check_project_id(project_id)
        # Lookup compartment when project ID is valid but no compartment is given.
        if not compartment_id:
            compartment_id = OCIResource.get_compartment_id(project_id)
    check_compartment_id(compartment_id)
    return compartment_id, project_id

def check_limit():
    limit = request.args.get("limit", 10)
    if isinstance(limit, str) and not limit.isdigit():
        abort_with_json_error(400, "limit parameter must be an integer.")
    return limit

def is_valid_ocid(resource_type, ocid):
    if re.match(r"ocid[0-9]." + resource_type + r".oc[0-9].[a-z-]+.[a-z0-9]+", ocid):
        return True
    if re.match(r"ocid[0-9]." + resource_type + r"int.oc[0-9].[a-z-]+.[a-z0-9]+", ocid):
        return True
    return False
