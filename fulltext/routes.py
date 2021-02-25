"""Provides the blueprint for the fulltext API."""

from typing import Optional, Callable, Any, List
from flask import request, Blueprint, Response, make_response
from flask.json import jsonify
from werkzeug.exceptions import NotAcceptable, BadRequest, NotFound
from arxiv import status
# from arxiv.users.domain import Session, Scope
# from arxiv.users.auth import scopes
# from arxiv.users.auth.decorators import scoped
from arxiv.base import logging
from fulltext import controllers
from .domain import SupportedBuckets, SupportedFormats

logger = logging.getLogger(__name__)

ARXIV_PREFIX = '/<id_type>/<arxiv:identifier>'
SUBMISSION_PREFIX = '/<id_type>/<source:identifier>'

blueprint = Blueprint('fulltext', __name__, url_prefix='')

Authorizer = Callable[[str, Optional[str]], bool]


# TODO: Auth disabled
# def make_authorizer(scope: Scope) -> Authorizer:
#     """Make an authorizer function for injection into a controller."""
#     def inner(identifier: str, owner_id: Optional[str]) -> bool:
#         """Check whether the session is authorized for a specific resource."""
#         logger.debug('Authorize for %s owned by %s', identifier, owner_id)
#         logger.debug('Client user id is %s', request.auth.user.user_id) # type: ignore
#         try:
#             source_id, checksum = identifier.split('/', 1)
#         except ValueError as e:
#             logger.debug('Bad identifier? %s', e)
#             raise NotFound('Unsupported identifier') from e
#         return (request.auth.is_authorized(scope, source_id) # type: ignore
#                 or (request.auth.user # type: ignore
#                     and str(request.auth.user.user_id) == owner_id)) # type: ignore
#     return inner


def resource_id(id_type: str, identifier: str, *args: Any, **kw: Any) -> str:
    """Get the resource ID for an endpoint."""
    if id_type == SupportedBuckets.SUBMISSION:
        return identifier.split('/', 1)[0]
    return identifier


def best_match(available: List[str], default: str) -> Optional[str]:
    """Determine best content type given Accept header and available types."""
    if 'Accept' not in request.headers:
        return default
    ctype: Optional[str] = request.accept_mimetypes.best_match(available)
    return ctype


@blueprint.route('/status')
def ok() -> Response:
    """Provide current integration status information for health checks."""
    data, code, headers = controllers.service_status()
    response: Response = make_response(jsonify(data), code, headers)
    return response



@blueprint.route(ARXIV_PREFIX, methods=['POST'])
@blueprint.route(SUBMISSION_PREFIX, methods=['POST'])
# @scoped(scopes.CREATE_FULLTEXT, resource=resource_id)
def start_extraction(id_type: str, identifier: str) -> Response:
    """Handle requests for fulltext extraction."""
    payload: Optional[dict] = request.get_json()
    force: bool = payload.get('force', False) if payload is not None else False
    token = request.environ['token']

    # Authorization is required to work with submissions.
    authorizer: Optional[Authorizer] = None
    # TODO: Auth disabled
    # if id_type == SupportedBuckets.SUBMISSION:
    #     authorizer = make_authorizer(scopes.READ_COMPILE)

    data, code, headers = \
        controllers.start_extraction(id_type, identifier, token, force=force,
                                     authorizer=authorizer)
    response: Response = make_response(jsonify(data), code, headers)
    return response


@blueprint.route(ARXIV_PREFIX + '/version/<version>/format/<content_fmt>')
@blueprint.route(ARXIV_PREFIX + '/version/<version>')
@blueprint.route(ARXIV_PREFIX + '/format/<content_fmt>')
@blueprint.route(ARXIV_PREFIX)
@blueprint.route(SUBMISSION_PREFIX + '/version/<version>/format/<content_fmt>')
@blueprint.route(SUBMISSION_PREFIX + '/version/<version>')
@blueprint.route(SUBMISSION_PREFIX + '/format/<content_fmt>')
@blueprint.route(SUBMISSION_PREFIX)
# @scoped(scopes.READ_FULLTEXT, resource=resource_id)
def retrieve(id_type: str, identifier: str, version: Optional[str] = None,
             content_fmt: str = SupportedFormats.PLAIN) -> Response:
    """Retrieve full-text content for an arXiv paper."""
    if identifier is None:
        raise BadRequest('identifier missing in request')
    available = ['application/json', 'text/plain']
    content_type = best_match(available, 'application/json')

    # Authorization is required to work with submissions.
    authorizer: Optional[Authorizer] = None
    # TODO: Auth disabled
    # if id_type == SupportedBuckets.SUBMISSION:
    #     authorizer = make_authorizer(scopes.READ_COMPILE)

    data, code, headers = controllers.retrieve(identifier, id_type, version,
                                               content_fmt=content_fmt,
                                               authorizer=authorizer)
    if content_type == 'text/plain':
        response_data = Response(data['content'], content_type='text/plain')
    elif content_type == 'application/json':
        if 'content' in data:
            data['content'] = data['content']
        response_data = jsonify(data)
    else:
        raise NotAcceptable('unsupported content type')
    response: Response = make_response(response_data, code, headers)
    return response


@blueprint.route(ARXIV_PREFIX + '/version/<version>/status')
@blueprint.route(ARXIV_PREFIX + '/status')
@blueprint.route(SUBMISSION_PREFIX + '/version/<version>/status')
@blueprint.route(SUBMISSION_PREFIX + '/status')
# @scoped(scopes.READ_FULLTEXT, resource=resource_id)
def task_status(id_type: str, identifier: str,
                version: Optional[str] = None) -> Response:
    """Get the status of a text extraction task."""
    # Authorization is required to work with submissions.
    authorizer: Optional[Authorizer] = None
    # TODO: Auth disabled
    # if id_type == SupportedBuckets.SUBMISSION:
    #     authorizer = make_authorizer(scopes.READ_COMPILE)

    data, code, headers = controllers.get_task_status(identifier, id_type,
                                                      version=version,
                                                      authorizer=authorizer)
    response: Response = make_response(jsonify(data), code, headers)
    return response
