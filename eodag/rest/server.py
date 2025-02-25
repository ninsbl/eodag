# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import logging
import os
import re
import traceback
from contextlib import asynccontextmanager
from importlib.metadata import version
from json import JSONDecodeError
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Optional,
)

from fastapi import APIRouter as FastAPIRouter
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import ORJSONResponse
from pydantic import ValidationError as pydanticValidationError
from pygeofilter.backends.cql2_json import to_cql2
from pygeofilter.parsers.cql2_text import parse as parse_cql2_text
from starlette.exceptions import HTTPException as StarletteHTTPException

from eodag.config import load_stac_api_config
from eodag.rest.cache import init_cache
from eodag.rest.core import (
    all_collections,
    download_stac_item,
    eodag_api_init,
    get_collection,
    get_detailled_collections_list,
    get_queryables,
    get_stac_api_version,
    get_stac_catalogs,
    get_stac_conformance,
    get_stac_extension_oseo,
    search_stac_items,
)
from eodag.rest.types.eodag_search import EODAGSearch
from eodag.rest.types.queryables import QueryablesGetParams
from eodag.rest.types.stac_search import SearchPostRequest, sortby2list
from eodag.rest.utils import format_pydantic_error, str2json, str2list
from eodag.utils import parse_header, update_nested_dict
from eodag.utils.exceptions import (
    AuthenticationError,
    DownloadError,
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    RequestError,
    TimeOutError,
    UnsupportedProductType,
    UnsupportedProvider,
    ValidationError,
)

if TYPE_CHECKING:
    from fastapi.types import DecoratedCallable
    from requests import Response

from starlette.responses import Response as StarletteResponse

logger = logging.getLogger("eodag.rest.server")
ERRORS_WITH_500_STATUS_CODE = {
    "MisconfiguredError",
    "AuthenticationError",
    "DownloadError",
    "RequestError",
}


class APIRouter(FastAPIRouter):
    """API router"""

    def api_route(
        self, path: str, *, include_in_schema: bool = True, **kwargs: Any
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        """Creates API route decorator"""
        if path == "/":
            return super().api_route(
                path, include_in_schema=include_in_schema, **kwargs
            )

        if path.endswith("/"):
            path = path[:-1]
        add_path = super().api_route(
            path, include_in_schema=include_in_schema, **kwargs
        )

        alternate_path = path + "/"
        add_alternate_path = super().api_route(
            alternate_path, include_in_schema=False, **kwargs
        )

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            add_alternate_path(func)
            return add_path(func)

        return decorator


router = APIRouter()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """API init and tear-down"""
    eodag_api_init()
    init_cache(app)
    yield


app = FastAPI(lifespan=lifespan, title="EODAG", docs_url="/api.html")

# conf from resources/stac_api.yml
stac_api_config = load_stac_api_config()


@router.api_route(
    methods=["GET", "HEAD"], path="/api", tags=["Capabilities"], include_in_schema=False
)
async def eodag_openapi(request: Request) -> Dict[str, Any]:
    """Customized openapi"""
    logger.debug("URL: /api")
    if app.openapi_schema:
        return app.openapi_schema

    root_catalog = await get_stac_catalogs(request=request, url="")
    stac_api_version = get_stac_api_version()

    openapi_schema = get_openapi(
        title=f"{root_catalog['title']} / eodag",
        version=version("eodag"),
        routes=app.routes,
    )

    # stac_api_config
    update_nested_dict(openapi_schema["paths"], stac_api_config["paths"])
    try:
        update_nested_dict(openapi_schema["components"], stac_api_config["components"])
    except KeyError:
        openapi_schema["components"] = stac_api_config["components"]
    openapi_schema["tags"] = stac_api_config["tags"]

    detailled_collections_list = get_detailled_collections_list()

    openapi_schema["info"]["description"] = (
        root_catalog["description"]
        + f" (stac-api-spec {stac_api_version})"
        + "<details><summary>Available collections / product types</summary>"
        + "".join(
            [
                f"[{pt['ID']}](/collections/{pt['ID']} '{pt['title']}') - "
                for pt in detailled_collections_list
            ]
        )[:-2]
        + "</details>"
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.__setattr__("openapi", eodag_openapi)

# Cross-Origin Resource Sharing
allowed_origins = os.getenv("EODAG_CORS_ALLOWED_ORIGINS")
allowed_origins_list = allowed_origins.split(",") if allowed_origins else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def forward_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Middleware that handles forward headers and sets request.state.url*"""

    forwarded_host = request.headers.get("x-forwarded-host", None)
    forwarded_proto = request.headers.get("x-forwarded-proto", None)

    if "forwarded" in request.headers:
        header_forwarded = parse_header(request.headers["forwarded"])
        forwarded_host = str(header_forwarded.get_param("host", None)) or forwarded_host
        forwarded_proto = (
            str(header_forwarded.get_param("proto", None)) or forwarded_proto
        )

    request.state.url_root = f"{forwarded_proto or request.url.scheme}://{forwarded_host or request.url.netloc}"
    request.state.url = f"{request.state.url_root}{request.url.path}"

    response = await call_next(request)
    return response


@app.exception_handler(StarletteHTTPException)
async def default_exception_handler(
    request: Request, error: HTTPException
) -> ORJSONResponse:
    """Default errors handle"""
    description = (
        getattr(error, "description", None)
        or getattr(error, "detail", None)
        or str(error)
    )
    return ORJSONResponse(
        status_code=error.status_code,
        content={"description": description},
    )


@app.exception_handler(ValidationError)
async def handle_invalid_usage_with_validation_error(
    request: Request, error: ValidationError
) -> ORJSONResponse:
    """Invalid usage [400] ValidationError handle"""
    if error.parameters:
        for error_param in error.parameters:
            stac_param = EODAGSearch.to_stac(error_param)
            error.message = error.message.replace(error_param, stac_param)
    logger.debug(traceback.format_exc())
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=400,
            detail=f"{type(error).__name__}: {str(error.message)}",
        ),
    )


@app.exception_handler(NoMatchingProductType)
@app.exception_handler(UnsupportedProductType)
@app.exception_handler(UnsupportedProvider)
async def handle_invalid_usage(request: Request, error: Exception) -> ORJSONResponse:
    """Invalid usage [400] errors handle"""
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=400,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@app.exception_handler(NotAvailableError)
async def handle_resource_not_found(
    request: Request, error: Exception
) -> ORJSONResponse:
    """Not found [404] errors handle"""
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=404,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@app.exception_handler(MisconfiguredError)
@app.exception_handler(AuthenticationError)
async def handle_auth_error(request: Request, error: Exception) -> ORJSONResponse:
    """These errors should be sent as internal server error to the client"""
    logger.error("%s: %s", type(error).__name__, str(error))
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=500,
            detail="Internal server error: please contact the administrator",
        ),
    )


@app.exception_handler(DownloadError)
async def handle_download_error(request: Request, error: Exception) -> ORJSONResponse:
    """DownloadError should be sent as internal server error with details to the client"""
    logger.error(f"{type(error).__name__}: {str(error)}")
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@app.exception_handler(RequestError)
async def handle_request_error(request: Request, error: RequestError) -> ORJSONResponse:
    """RequestError should be sent as internal server error with details to the client"""
    if getattr(error, "history", None):
        error_history_tmp = list(error.history)
        for i, search_error in enumerate(error_history_tmp):
            if search_error[1].__class__.__name__ in ERRORS_WITH_500_STATUS_CODE:
                search_error[1].args = ("an internal error occured",)
                error_history_tmp[i] = search_error
                continue
            if getattr(error, "parameters", None):
                for error_param in error.parameters:
                    stac_param = EODAGSearch.to_stac(error_param)
                    search_error[1].args = (
                        search_error[1].args[0].replace(error_param, stac_param),
                    )
                    error_history_tmp[i] = search_error
        error.history = set(error_history_tmp)
    logger.error(f"{type(error).__name__}: {str(error)}")
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@app.exception_handler(TimeOutError)
async def handle_timeout(request: Request, error: Exception) -> ORJSONResponse:
    """Timeout [504] errors handle"""
    logger.error(f"{type(error).__name__}: {str(error)}")
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=504,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@router.api_route(methods=["GET", "HEAD"], path="/", tags=["Capabilities"])
async def catalogs_root(request: Request) -> ORJSONResponse:
    """STAC catalogs root"""
    logger.debug("URL: %s", request.url)

    response = await get_stac_catalogs(
        request=request,
        url=request.state.url,
        provider=request.query_params.get("provider", None),
    )

    return ORJSONResponse(response)


@router.api_route(methods=["GET", "HEAD"], path="/conformance", tags=["Capabilities"])
def conformance() -> ORJSONResponse:
    """STAC conformance"""
    logger.debug("URL: /conformance")
    response = get_stac_conformance()

    return ORJSONResponse(response)


@router.api_route(
    methods=["GET", "HEAD"],
    path="/extensions/oseo/json-schema/schema.json",
    include_in_schema=False,
)
def stac_extension_oseo(request: Request) -> ORJSONResponse:
    """STAC OGC / OpenSearch extension for EO"""
    logger.debug("URL: %s", request.url)
    response = get_stac_extension_oseo(url=request.state.url)

    return ORJSONResponse(response)


@router.api_route(
    methods=["GET", "HEAD"],
    path="/collections/{collection_id}/items/{item_id}/download",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_item_download(
    collection_id: str, item_id: str, request: Request
) -> StarletteResponse:
    """STAC collection item download"""
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    return download_stac_item(
        request=request,
        catalogs=[collection_id],
        item_id=item_id,
        provider=provider,
        **arguments,
    )


@router.api_route(
    methods=["GET", "HEAD"],
    path="/collections/{collection_id}/items/{item_id}/download/{asset}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_item_download_asset(
    collection_id: str, item_id: str, asset: str, request: Request
):
    """STAC collection item asset download"""
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    return download_stac_item(
        request=request,
        catalogs=[collection_id],
        item_id=item_id,
        provider=provider,
        asset=asset,
    )


@router.api_route(
    methods=["GET", "HEAD"],
    path="/collections/{collection_id}/items/{item_id}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_item(
    collection_id: str, item_id: str, request: Request, provider: Optional[str] = None
) -> ORJSONResponse:
    """STAC collection item by id"""
    logger.debug("URL: %s", request.url)

    search_request = SearchPostRequest(
        provider=provider, ids=[item_id], collections=[collection_id], limit=1
    )

    item_collection = search_stac_items(request, search_request)

    if not item_collection["features"]:
        raise HTTPException(
            status_code=404,
            detail=f"Item {item_id} in Collection {collection_id} does not exist.",
        )

    return ORJSONResponse(item_collection["features"][0])


@router.api_route(
    methods=["GET", "HEAD"],
    path="/collections/{collection_id}/items",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_items(
    collection_id: str,
    request: Request,
    provider: Optional[str] = None,
    bbox: Optional[str] = None,
    datetime: Optional[str] = None,
    limit: Optional[int] = None,
    query: Optional[str] = None,
    page: Optional[int] = None,
    sortby: Optional[str] = None,
    filter: Optional[str] = None,
    filter_lang: Optional[str] = "cql2-text",
    crunch: Optional[str] = None,
) -> ORJSONResponse:
    """Fetch collection's features"""

    return get_search(
        request=request,
        provider=provider,
        collections=collection_id,
        bbox=bbox,
        datetime=datetime,
        limit=limit,
        query=query,
        page=page,
        sortby=sortby,
        filter=filter,
        filter_lang=filter_lang,
        crunch=crunch,
    )


@router.api_route(
    methods=["GET", "HEAD"],
    path="/collections/{collection_id}/queryables",
    tags=["Capabilities"],
    include_in_schema=False,
    response_model_exclude_none=True,
)
async def list_collection_queryables(
    request: Request,
    collection_id: str,
) -> ORJSONResponse:
    """Returns the list of queryable properties for a specific collection.

    This endpoint provides a list of properties that can be used as filters when querying
    the specified collection. These properties correspond to characteristics of the data
    that can be filtered using comparison operators.

    :param request: The incoming request object.
    :type request: fastapi.Request
    :param collection_id: The identifier of the collection for which to retrieve queryable properties.
    :type collection_id: str
    :returns: A json object containing the list of available queryable properties for the specified collection.
    :rtype: Any
    """
    logger.debug(f"URL: {request.url}")
    additional_params = dict(request.query_params)
    provider = additional_params.pop("provider", None)

    queryables = await get_queryables(
        request,
        QueryablesGetParams(collection=collection_id, **additional_params),
        provider=provider,
    )

    return ORJSONResponse(queryables)


@router.api_route(
    methods=["GET", "HEAD"],
    path="/collections/{collection_id}",
    tags=["Capabilities"],
    include_in_schema=False,
)
async def collection_by_id(
    collection_id: str, request: Request, provider: Optional[str] = None
) -> ORJSONResponse:
    """STAC collection by id"""
    logger.debug("URL: %s", request.url)

    response = await get_collection(
        request=request,
        collection_id=collection_id,
        provider=provider,
    )

    return ORJSONResponse(response)


@router.api_route(
    methods=["GET", "HEAD"],
    path="/collections",
    tags=["Capabilities"],
    include_in_schema=False,
)
async def collections(
    request: Request,
    provider: Optional[str] = None,
    q: Optional[str] = None,
    platform: Optional[str] = None,
    instrument: Optional[str] = None,
    constellation: Optional[str] = None,
    datetime: Optional[str] = None,
) -> ORJSONResponse:
    """STAC collections

    Can be filtered using parameters: instrument, platform, platformSerialIdentifier, sensorType,
    processingLevel
    """
    logger.debug("URL: %s", request.url)

    collections = await all_collections(
        request, provider, q, platform, instrument, constellation, datetime
    )
    return ORJSONResponse(collections)


@router.api_route(
    methods=["GET", "HEAD"],
    path="/catalogs/{catalogs:path}/items/{item_id}/download",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_item_download(
    catalogs: str, item_id: str, request: Request
) -> StarletteResponse:
    """STAC Catalog item download"""
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    list_catalog = catalogs.strip("/").split("/")

    return download_stac_item(
        request=request,
        catalogs=list_catalog,
        item_id=item_id,
        provider=provider,
        **arguments,
    )


@router.api_route(
    methods=["GET", "HEAD"],
    path="/catalogs/{catalogs:path}/items/{item_id}/download/{asset_filter}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_item_download_asset(
    catalogs: str, item_id: str, asset_filter: str, request: Request
):
    """STAC Catalog item asset download"""
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    list_catalog = catalogs.strip("/").split("/")

    return download_stac_item(
        request,
        catalogs=list_catalog,
        item_id=item_id,
        provider=provider,
        asset=asset_filter,
        **arguments,
    )


@router.api_route(
    methods=["GET", "HEAD"],
    path="/catalogs/{catalogs:path}/items/{item_id}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_item(
    catalogs: str, item_id: str, request: Request, provider: Optional[str] = None
):
    """Fetch catalog's single features."""
    logger.debug("URL: %s", request.url)

    list_catalog = catalogs.strip("/").split("/")

    search_request = SearchPostRequest(provider=provider, ids=[item_id], limit=1)

    item_collection = search_stac_items(request, search_request, catalogs=list_catalog)

    if not item_collection["features"]:
        raise HTTPException(
            status_code=404,
            detail=f"Item {item_id} in Catalog {catalogs} does not exist.",
        )

    return ORJSONResponse(item_collection["features"][0])


@router.api_route(
    methods=["GET", "HEAD"],
    path="/catalogs/{catalogs:path}/items",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_items(
    catalogs: str,
    request: Request,
    provider: Optional[str] = None,
    bbox: Optional[str] = None,
    datetime: Optional[str] = None,
    limit: Optional[int] = None,
    page: Optional[int] = None,
    sortby: Optional[str] = None,
    crunch: Optional[str] = None,
) -> ORJSONResponse:
    """Fetch catalog's features"""
    logger.debug("URL: %s", request.state.url)

    base_args = {
        "provider": provider,
        "datetime": datetime,
        "bbox": str2list(bbox),
        "limit": limit,
        "page": page,
        "sortby": sortby2list(sortby),
        "crunch": crunch,
    }

    clean = {k: v for k, v in base_args.items() if v is not None and v != []}

    list_catalog = catalogs.strip("/").split("/")

    try:
        search_request = SearchPostRequest.model_validate(clean)
    except pydanticValidationError as e:
        raise HTTPException(status_code=400, detail=format_pydantic_error(e)) from e

    response = search_stac_items(
        request=request,
        search_request=search_request,
        catalogs=list_catalog,
    )
    return ORJSONResponse(response)


@router.api_route(
    methods=["GET", "HEAD"],
    path="/catalogs/{catalogs:path}",
    tags=["Capabilities"],
    include_in_schema=False,
)
async def stac_catalogs(
    catalogs: str, request: Request, provider: Optional[str] = None
) -> ORJSONResponse:
    """Describe the given catalog and list available sub-catalogs"""
    logger.debug("URL: %s", request.url)

    if not catalogs:
        raise HTTPException(
            status_code=404,
            detail="Not found",
        )

    list_catalog = catalogs.strip("/").split("/")
    response = await get_stac_catalogs(
        request=request,
        url=request.state.url,
        catalogs=tuple(list_catalog),
        provider=provider,
    )
    return ORJSONResponse(response)


@router.api_route(
    methods=["GET", "HEAD"],
    path="/queryables",
    tags=["Capabilities"],
    response_model_exclude_none=True,
    include_in_schema=False,
)
async def list_queryables(request: Request) -> ORJSONResponse:
    """Returns the list of terms available for use when writing filter expressions.

    This endpoint provides a list of terms that can be used as filters when querying
    the data. These terms correspond to properties that can be filtered using comparison
    operators.

    :param request: The incoming request object.
    :type request: fastapi.Request
    :returns: A json object containing the list of available queryable terms.
    :rtype: Any
    """
    logger.debug(f"URL: {request.url}")
    additional_params = dict(request.query_params.items())
    provider = additional_params.pop("provider", None)
    queryables = await get_queryables(
        request, QueryablesGetParams(**additional_params), provider=provider
    )

    return ORJSONResponse(queryables)


@router.api_route(
    methods=["GET", "HEAD"],
    path="/search",
    tags=["STAC"],
    include_in_schema=False,
)
def get_search(
    request: Request,
    provider: Optional[str] = None,
    collections: Optional[str] = None,
    ids: Optional[str] = None,
    bbox: Optional[str] = None,
    datetime: Optional[str] = None,
    intersects: Optional[str] = None,
    limit: Optional[int] = None,
    query: Optional[str] = None,
    page: Optional[int] = None,
    sortby: Optional[str] = None,
    filter: Optional[str] = None,  # pylint: disable=redefined-builtin
    filter_lang: Optional[str] = "cql2-text",
    crunch: Optional[str] = None,
) -> ORJSONResponse:
    """Handler for GET /search"""
    logger.debug("URL: %s", request.state.url)

    query_params = str(request.query_params)

    # Kludgy fix because using factory does not allow alias for filter-lang
    if filter_lang is None:
        match = re.search(r"filter-lang=([a-z0-9-]+)", query_params, re.IGNORECASE)
        if match:
            filter_lang = match.group(1)

    base_args = {
        "provider": provider,
        "collections": str2list(collections),
        "ids": str2list(ids),
        "datetime": datetime,
        "bbox": str2list(bbox),
        "intersects": str2json("intersects", intersects),
        "limit": limit,
        "query": str2json("query", query),
        "page": page,
        "sortby": sortby2list(sortby),
        "crunch": crunch,
    }

    if filter:
        if filter_lang == "cql2-text":
            ast = parse_cql2_text(filter)
            base_args["filter"] = str2json("filter", to_cql2(ast))  # type: ignore
            base_args["filter-lang"] = "cql2-json"
        elif filter_lang == "cql-json":
            base_args["filter"] = str2json(filter)

    clean = {k: v for k, v in base_args.items() if v is not None and v != []}

    try:
        search_request = SearchPostRequest.model_validate(clean)
    except pydanticValidationError as e:
        raise HTTPException(status_code=400, detail=format_pydantic_error(e)) from e

    response = search_stac_items(
        request=request,
        search_request=search_request,
    )
    return ORJSONResponse(content=response, media_type="application/json")


@router.api_route(
    methods=["POST", "HEAD"],
    path="/search",
    tags=["STAC"],
    include_in_schema=False,
)
async def post_search(request: Request) -> ORJSONResponse:
    """STAC post search"""
    logger.debug("URL: %s", request.url)

    content_type = request.headers.get("Content-Type")

    if content_type is None:
        raise HTTPException(status_code=400, detail="No Content-Type provided")
    if content_type != "application/json":
        raise HTTPException(status_code=400, detail="Content-Type not supported")

    try:
        payload = await request.json()
    except JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON data") from e

    try:
        search_request = SearchPostRequest.model_validate(payload)
    except pydanticValidationError as e:
        raise HTTPException(status_code=400, detail=format_pydantic_error(e)) from e

    logger.debug("Body: %s", search_request.model_dump(exclude_none=True))

    response = search_stac_items(
        request=request,
        search_request=search_request,
    )
    return ORJSONResponse(content=response, media_type="application/json")


app.include_router(router)
