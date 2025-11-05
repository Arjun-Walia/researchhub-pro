"""Export API endpoints."""
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import io

from app.models import Query
from app.services.export_service import ExportService
from app.services.analytics_service import AnalyticsService


bp = Blueprint('export', __name__)
logger = logging.getLogger(__name__)
export_service = ExportService()
analytics = AnalyticsService()


@bp.route('/query/<int:query_id>', methods=['GET'])
@jwt_required()
def export_query(query_id):
    """
    Export query results in specified format.
    
    Query params:
        - format: Export format (json, csv, markdown, html, txt, xlsx)
    
    Returns:
        Exported data
    """
    try:
        user_id = get_jwt_identity()
        format_type = request.args.get('format', 'json').lower()
        
        if format_type not in export_service.supported_formats:
            return jsonify({'error': f'Unsupported format: {format_type}'}), 400
        
        # Get query and results
        query = Query.query.filter_by(id=query_id, user_id=user_id).first()
        
        if not query:
            return jsonify({'error': 'Query not found'}), 404
        
        # Prepare data for export
        results = [r.to_dict() for r in query.results]
        export_data = {
            'query': query.query_text,
            'results': results,
            'total_results': len(results),
            'created_at': query.created_at.isoformat() if query.created_at else None
        }
        
        # Export
        exported = export_service.export(export_data, format_type)
        
        # Track activity
        analytics.track_activity(
            user_id=user_id,
            activity_type='export',
            resource_type='query',
            resource_id=query_id,
            metadata={'format': format_type}
        )
        
        # Return based on format
        if format_type == 'xlsx':
            return send_file(
                io.BytesIO(exported),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'research_results_{query_id}.xlsx'
            )
        else:
            mime_types = {
                'json': 'application/json',
                'csv': 'text/csv',
                'markdown': 'text/markdown',
                'html': 'text/html',
                'txt': 'text/plain'
            }
            
            return exported, 200, {
                'Content-Type': mime_types.get(format_type, 'text/plain'),
                'Content-Disposition': f'attachment; filename=research_results_{query_id}.{format_type}'
            }
        
    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500
