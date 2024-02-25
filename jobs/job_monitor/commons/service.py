import oci
from flask import jsonify
from commons.auth import get_authentication


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


def list_shapes(compartment_ocid, profile=None):
    client = oci.data_science.DataScienceClient(
        **get_authentication(profile_name=profile)
    )
    shapes = [
        shape.name
        for shape in oci.pagination.list_call_get_all_results(
            client.list_job_shapes,
            compartment_ocid,
        ).data
    ]
    fast_launch_shapes = [
        shape.shape_name
        for shape in oci.pagination.list_call_get_all_results(
            client.list_fast_launch_job_configs,
            compartment_ocid,
        ).data
    ]
    return jsonify(
        {
            "supported_shapes": shapes,
            "fast_launch_shapes": fast_launch_shapes,
        }
    )
