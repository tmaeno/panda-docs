# Functions in the following list will not be included in the API documentation
EXCLUDED_FUNCTIONS = ["init_task_buffer"]

# Parameters in the following list will not be included in the API documentation.
# This expects the parameter naming to be consistent.
EXCLUDED_PARAMS = ["req"]

# General description at the top of the documentation
DESCRIPTION = """
### Protocol: we generally require communication over HTTPS. The server will not accept HTTP requests unless explicitly mentioned.

### HTTP methods:
* GET: Retrieve data from the server. Parameters have to be sent **in the URL**. List parameters are passed by repeating the parameter name (e.g. `?job_ids=1&job_ids=2`).
```
export pandaurl=https://pandaserver.cern.ch:25443
  curl --capath "${X509_CERT_DIR}" \
    --cert "${X509_USER_PROXY}" \
    --key "${X509_USER_PROXY}" \
    "${pandaurl}/api/v1/task/get_status?task_id=12345"
```
* PUT: Update data on the server. Parameters have to be sent **in the body** in json encoded format. When the client wants to gzip the data, the content encoding has to be set accordingly.
```
export pandaurl=https://pandaserver.cern.ch:25443
curl --capath "${X509_CERT_DIR}" \
  --cert "${X509_USER_PROXY}" \
  --key "${X509_USER_PROXY}" \
  --json '{"task_id": 12345}' \
  "${pandaurl}/api/v1/file_server/upload_file_recovery_request"
```

### Response formats: 
The return codes are usually specified with each API function, but in general:
* 200: Function called correctly and response will be `Content-type: application/json`. This does not necessarily mean that the operation was successful, but that the function was called correctly.     Reasons why the operation could fail are:
    * Wrong parameters or the JSON could not be decoded.
    * The function was called using the wrong HTTP method (e.g. GET instead of PUT).  
    * The function expects authentication (certificate/token) and it was not provided.
    * The function expects production role and it was not provided.
    * Caught exceptions when interacting with the database.
    
The usual response dictionary has the following format:
```
{ "success": True/False, "message": "Usually an error when there was a failure. The message can generally be ignored if the operation was successful.", "data": "The data returned if the operation was successful." }
```
* 403: Forbidden. The client called a forbidden function or there was an authentication issue. The response will use `Content-type: text/plain`.
* 500: Server crashed calling the method. The response will use `Content-type: text/plain`.
* 503: The server is overloaded. The call did not reach PanDA and the response comes from directly `httpd`. 
"""

# Default response template for all the API methods
DEFAULT_RESPONSE_TEMPLATE = {
    "200": {
        "description": "Method called correctly",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "example": True,
                            "description": "Indicates whether the request was successful (True) or not (False)",
                        },
                        "message": {
                            "type": "string",
                            "description": "Message indicating the nature of the failure. Empty or meaningless if the request was successful.",
                        },
                        "data": {
                            "type": "object",
                            "description": "The data returned if the operation is successful. Null if it fails or the method does not generate return data.",
                        },
                    },
                    "required": ["success", "message", "data"],
                }
            }
        },
    },
    "403": {
        "description": "Forbidden",
        "content": {
            "text/plain": {
                "schema": {
                    "type": "string",
                    "example": "You are calling an undefined method is not allowed for the requested URL",
                }
            }
        },
    },
    "404": {
        "description": "Not Found",
        "content": {
            "text/plain": {
                "schema": {"type": "string", "example": "Resource not found"}
            }
        },
    },
    "500": {
        "description": "INTERNAL SERVER ERROR",
        "content": {
            "text/plain": {
                "schema": {
                    "type": "string",
                    "example": "INTERNAL SERVER ERROR. The server encountered an internal error and was unable to complete your request.",
                }
            }
        },
    },
}
