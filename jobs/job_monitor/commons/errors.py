import functools

import oci
from flask import abort, jsonify, make_response


def abort_with_json_error(code, message):
    abort(make_response(jsonify(error=code, message=message), code))


def handle_service_exception(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except oci.exceptions.ServiceError as ex:
            return make_response(
                jsonify(
                    {
                        "error": ex.code,
                        "message": ex.message,
                    }
                ),
                ex.status,
            )
        return func(*args, **kwargs)

    return wrapper
