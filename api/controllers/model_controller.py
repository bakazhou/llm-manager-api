"""Model management controller"""
import logging
from urllib.parse import unquote

from flask import request, current_app
from flask_restful import Resource

from ..services.model_service import ModelService
from ..utils.exceptions import ValidationError, ModelNotFoundError, ExternalServiceError
from ..utils.helpers import format_response, format_error_response
from ..utils.validators import validate_model_id

logger = logging.getLogger(__name__)


class ModelController:
    """Model controller"""

    def __init__(self):
        self.model_service = ModelService(current_app.config)

    def search_models(self):
        """Search models"""
        try:
            # Get query parameters
            params = {
                'query': request.args.get('query', ''),
                'page': request.args.get('page', 1),
                'page_size': request.args.get('page_size', 20),
                'source': request.args.get('source', ''),
                'model_type': request.args.get('model_type', ''),
                'sort_by': request.args.get('sort_by', 'downloads'),  # Default to sort by downloads
                'sort_order': request.args.get('sort_order', 'desc'),
                'tags': request.args.get('tags', ''),
                'is_featured': request.args.get('is_featured')
            }

            logger.info(f"Model search request: {params}")

            # If no search keywords, record this as a trending models request
            if not params['query'] or params['query'].strip() == '':
                logger.info("No search keywords provided, returning trending models for quality assurance")

            # Call service layer to search
            result = self.model_service.search_models(params)

            # Record the number of returned models and source
            models_count = len(result.get('items', []))
            logger.info(f"Search completed, returning {models_count} models")

            return format_response(
                data=result,
                message="Search successful"
            )

        except ValidationError as e:
            logger.warning(f"Parameter validation failed: {e.message}")
            return format_error_response(
                message=e.message,
                error_code=e.code,
                details={'field': getattr(e, 'field', None)}
            ), e.status_code

        except ExternalServiceError as e:
            logger.error(f"External service error: {e.message}")
            return format_error_response(
                message=e.message,
                error_code=e.code
            ), e.status_code

        except Exception as e:
            logger.error(f"Model search failed: {e}")
            return format_error_response(
                message="Model search failed, please try again later",
                error_code="SEARCH_ERROR"
            ), 500

    def get_model_info(self, model_id: str):
        """Get model detailed information"""
        try:
            # URL decode
            model_id = unquote(model_id)

            # Get source parameter
            source = request.args.get('source')

            logger.info(f"Get model info: {model_id}, source: {source}")

            # Call service layer to get model information
            model_info = self.model_service.get_model_info(model_id, source)

            return format_response(
                data=model_info,
                message="Get model info successful"
            )

        except ValidationError as e:
            logger.warning(f"Parameter validation failed: {e.message}")
            return format_error_response(
                message=e.message,
                error_code=e.code,
                details={'field': getattr(e, 'field', None)}
            ), e.status_code

        except ModelNotFoundError as e:
            logger.warning(f"Model not found: {e.message}")
            return format_error_response(
                message=e.message,
                error_code=e.code,
                details={'model_id': model_id}
            ), e.status_code

        except ExternalServiceError as e:
            logger.error(f"External service error: {e.message}")
            return format_error_response(
                message=e.message,
                error_code=e.code
            ), e.status_code

        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return format_error_response(
                message="Failed to get model info, please try again later",
                error_code="GET_MODEL_ERROR"
            ), 500

    def get_model_categories(self):
        """Get model category list"""
        try:
            # Get source parameter
            source = request.args.get('source')

            logger.info(f"Get model categories: source={source}")

            # Call service layer to get categories
            categories = self.model_service.get_model_categories(source)

            return format_response(
                data={'categories': categories},
                message="Get model categories successful"
            )

        except Exception as e:
            logger.error(f"Failed to get model categories: {e}")
            return format_error_response(
                message="Failed to get model categories, please try again later",
                error_code="GET_CATEGORIES_ERROR"
            ), 500

    def get_trending_models(self):
        """Get trending models"""
        try:
            # Get parameters
            limit = int(request.args.get('limit', 10))
            source = request.args.get('source')

            # Limit range
            if limit < 1 or limit > 50:
                limit = 10

            logger.info(f"Get trending models: limit={limit}, source={source}")

            # Call service layer to get trending models
            trending_models = self.model_service.get_trending_models(limit, source)

            return format_response(
                data={'models': trending_models},
                message="Get trending models successful"
            )

        except Exception as e:
            logger.error(f"Failed to get trending models: {e}")
            return format_error_response(
                message="Failed to get trending models, please try again later",
                error_code="GET_TRENDING_ERROR"
            ), 500

    def get_model_stats(self):
        """Get model statistics information"""
        try:
            # Get source parameter
            source = request.args.get('source')

            logger.info(f"Get model stats: source={source}")

            # Call service layer to get statistics information
            stats = self.model_service.get_model_stats(source)

            return format_response(
                data=stats,
                message="Get statistics information successful"
            )

        except Exception as e:
            logger.error(f"Failed to get model stats: {e}")
            return format_error_response(
                message="Failed to get model stats, please try again later",
                error_code="GET_STATS_ERROR"
            ), 500

    def favorite_model(self, model_id: str):
        """Favorite model"""
        try:
            # URL decode
            model_id = unquote(model_id)

            # Validate model ID
            model_id = validate_model_id(model_id)

            logger.info(f"Favorite model: {model_id}")

            # Call service layer to favorite model
            success = self.model_service.favorite_model(model_id)

            if success:
                return format_response(
                    data={'model_id': model_id, 'favorited': True},
                    message="Favorite successful"
                )
            else:
                return format_error_response(
                    message="Favorite failed",
                    error_code="FAVORITE_ERROR"
                ), 500

        except ValidationError as e:
            logger.warning(f"Parameter validation failed: {e.message}")
            return format_error_response(
                message=e.message,
                error_code=e.code,
                details={'field': getattr(e, 'field', None)}
            ), e.status_code

        except Exception as e:
            logger.error(f"Failed to favorite model: {e}")
            return format_error_response(
                message="Favorite failed, please try again later",
                error_code="FAVORITE_ERROR"
            ), 500

    def unfavorite_model(self, model_id: str):
        """Unfavorite model"""
        try:
            # URL decode
            model_id = unquote(model_id)

            # Validate model ID
            model_id = validate_model_id(model_id)

            logger.info(f"Unfavorite model: {model_id}")

            # Call service layer to unfavorite
            success = self.model_service.unfavorite_model(model_id)

            if success:
                return format_response(
                    data={'model_id': model_id, 'favorited': False},
                    message="Unfavorite successful"
                )
            else:
                return format_error_response(
                    message="Unfavorite failed",
                    error_code="UNFAVORITE_ERROR"
                ), 500

        except ValidationError as e:
            logger.warning(f"Parameter validation failed: {e.message}")
            return format_error_response(
                message=e.message,
                error_code=e.code,
                details={'field': getattr(e, 'field', None)}
            ), e.status_code

        except Exception as e:
            logger.error(f"Failed to unfavorite model: {e}")
            return format_error_response(
                message="Unfavorite failed, please try again later",
                error_code="UNFAVORITE_ERROR"
            ), 500

    def sync_models(self):
        """Sync model information"""
        try:
            # Get parameters
            source = request.args.get('source', '').strip()
            limit = int(request.args.get('limit', 100))

            # Validate source
            if not source or source not in ['huggingface', 'ollama']:
                return format_error_response(
                    message="Source parameter must be 'huggingface' or 'ollama'",
                    error_code="VALIDATION_ERROR"
                ), 400

            # Limit quantity
            if limit < 1 or limit > 1000:
                limit = 100

            logger.info(f"Sync models: source={source}, limit={limit}")

            # Call service layer to sync models
            synced_count = self.model_service.sync_models_from_source(source, limit)

            return format_response(
                data={
                    'source': source,
                    'synced_count': synced_count,
                    'limit': limit
                },
                message=f"Sync completed, {synced_count} models synced"
            )

        except Exception as e:
            logger.error(f"Failed to sync models: {e}")
            return format_error_response(
                message="Sync failed, please try again later",
                error_code="SYNC_ERROR"
            ), 500


# Flask-RESTful Resource class
class ModelSearchResource(Resource):
    """Model search resource"""

    def __init__(self):
        self.controller = ModelController()

    def get(self):
        """GET /api/models/search"""
        return self.controller.search_models()


class ModelInfoResource(Resource):
    """Model information resource"""

    def __init__(self):
        self.controller = ModelController()

    def get(self, model_id):
        """GET /api/models/{model_id}/info"""
        return self.controller.get_model_info(model_id)


class ModelCategoriesResource(Resource):
    """Model category resource"""

    def __init__(self):
        self.controller = ModelController()

    def get(self):
        """GET /api/models/categories"""
        return self.controller.get_model_categories()


class ModelTrendingResource(Resource):
    """Trending model resource"""

    def __init__(self):
        self.controller = ModelController()

    def get(self):
        """GET /api/models/trending"""
        return self.controller.get_trending_models()


class ModelStatsResource(Resource):
    """Model statistics resource"""

    def __init__(self):
        self.controller = ModelController()

    def get(self):
        """GET /api/models/stats"""
        return self.controller.get_model_stats()


class ModelFavoriteResource(Resource):
    """Model favorite resource"""

    def __init__(self):
        self.controller = ModelController()

    def post(self, model_id):
        """POST /api/models/{model_id}/favorite"""
        return self.controller.favorite_model(model_id)

    def delete(self, model_id):
        """DELETE /api/models/{model_id}/favorite"""
        return self.controller.unfavorite_model(model_id)


class ModelSyncResource(Resource):
    """Model sync resource"""

    def __init__(self):
        self.controller = ModelController()

    def post(self):
        """POST /api/models/sync"""
        return self.controller.sync_models()
