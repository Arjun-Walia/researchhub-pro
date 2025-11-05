"""Analytics service for tracking and reporting."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import func

from app.models import UserActivity, SearchAnalytics, SystemMetrics, User, Query
from app.models.base import db


logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics and metrics collection."""
    
    def track_activity(
        self,
        user_id: int,
        activity_type: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        metadata: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Track user activity.
        
        Args:
            user_id: User ID
            activity_type: Type of activity
            resource_type: Type of resource
            resource_id: Resource ID
            metadata: Additional metadata
            ip_address: User IP address
            user_agent: User agent string
        """
        try:
            activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata=metadata,
                ip_address=ip_address,
                user_agent=user_agent
            )
            activity.save()
            logger.debug(f"Tracked activity: {activity_type} for user {user_id}")
        except Exception as e:
            logger.error(f"Activity tracking failed: {str(e)}")
    
    def track_search(
        self,
        query_id: Optional[int],
        query_text: str,
        result_count: int,
        execution_time: float,
        user_tier: str,
        search_domain: Optional[str] = None
    ):
        """Track search query for analytics."""
        try:
            analytics = SearchAnalytics(
                query_id=query_id,
                query_text=query_text,
                result_count=result_count,
                execution_time=execution_time,
                user_tier=user_tier,
                search_domain=search_domain
            )
            analytics.save()
            logger.debug(f"Tracked search: {query_text[:50]}")
        except Exception as e:
            logger.error(f"Search tracking failed: {str(e)}")
    
    def record_metric(
        self,
        metric_name: str,
        metric_value: float,
        metric_unit: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[Dict] = None
    ):
        """Record system metric."""
        try:
            metric = SystemMetrics(
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                category=category,
                tags=tags
            )
            metric.save()
        except Exception as e:
            logger.error(f"Metric recording failed: {str(e)}")
    
    def get_user_activity_summary(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get user activity summary.
        
        Args:
            user_id: User ID
            days: Number of days to look back
            
        Returns:
            Activity summary
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            activities = UserActivity.query.filter(
                UserActivity.user_id == user_id,
                UserActivity.created_at >= since
            ).all()
            
            # Aggregate by activity type
            activity_counts = {}
            for activity in activities:
                activity_type = activity.activity_type
                activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
            
            return {
                'user_id': user_id,
                'period_days': days,
                'total_activities': len(activities),
                'activity_breakdown': activity_counts,
                'last_activity': activities[-1].created_at.isoformat() if activities else None
            }
            
        except Exception as e:
            logger.error(f"Activity summary failed: {str(e)}")
            return {}
    
    def get_search_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get search analytics summary.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Search analytics summary
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            # Total searches
            total_searches = SearchAnalytics.query.filter(
                SearchAnalytics.created_at >= since
            ).count()
            
            # Average execution time
            avg_time = db.session.query(
                func.avg(SearchAnalytics.execution_time)
            ).filter(
                SearchAnalytics.created_at >= since
            ).scalar()
            
            # Average results per search
            avg_results = db.session.query(
                func.avg(SearchAnalytics.result_count)
            ).filter(
                SearchAnalytics.created_at >= since
            ).scalar()
            
            # Searches by tier
            tier_breakdown = db.session.query(
                SearchAnalytics.user_tier,
                func.count(SearchAnalytics.id)
            ).filter(
                SearchAnalytics.created_at >= since
            ).group_by(SearchAnalytics.user_tier).all()
            
            return {
                'period_days': days,
                'total_searches': total_searches,
                'avg_execution_time': float(avg_time) if avg_time else 0,
                'avg_results_per_search': float(avg_results) if avg_results else 0,
                'searches_by_tier': dict(tier_breakdown)
            }
            
        except Exception as e:
            logger.error(f"Search analytics failed: {str(e)}")
            return {}
    
    def get_system_metrics(
        self,
        metric_name: Optional[str] = None,
        category: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get system metrics.
        
        Args:
            metric_name: Filter by metric name
            category: Filter by category
            hours: Hours to look back
            
        Returns:
            List of metrics
        """
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            query = SystemMetrics.query.filter(SystemMetrics.created_at >= since)
            
            if metric_name:
                query = query.filter(SystemMetrics.metric_name == metric_name)
            
            if category:
                query = query.filter(SystemMetrics.category == category)
            
            metrics = query.order_by(SystemMetrics.created_at.desc()).all()
            
            return [m.to_dict() for m in metrics]
            
        except Exception as e:
            logger.error(f"System metrics retrieval failed: {str(e)}")
            return []
    
    def get_popular_queries(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most popular search queries.
        
        Args:
            days: Days to analyze
            limit: Number of results
            
        Returns:
            List of popular queries
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            popular = db.session.query(
                SearchAnalytics.query_text,
                func.count(SearchAnalytics.id).label('count')
            ).filter(
                SearchAnalytics.created_at >= since
            ).group_by(
                SearchAnalytics.query_text
            ).order_by(
                func.count(SearchAnalytics.id).desc()
            ).limit(limit).all()
            
            return [
                {'query': q, 'count': c}
                for q, c in popular
            ]
            
        except Exception as e:
            logger.error(f"Popular queries retrieval failed: {str(e)}")
            return []
    
    def get_user_growth(self, days: int = 30) -> Dict[str, Any]:
        """
        Get user growth statistics.
        
        Args:
            days: Days to analyze
            
        Returns:
            User growth data
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            # New users
            new_users = User.query.filter(User.created_at >= since).count()
            
            # Active users (logged in)
            active_users = User.query.filter(
                User.last_login_at >= since
            ).count()
            
            # Total users
            total_users = User.query.count()
            
            # Users by tier
            tier_breakdown = db.session.query(
                User.tier,
                func.count(User.id)
            ).group_by(User.tier).all()
            
            return {
                'period_days': days,
                'new_users': new_users,
                'active_users': active_users,
                'total_users': total_users,
                'users_by_tier': {str(tier): count for tier, count in tier_breakdown}
            }
            
        except Exception as e:
            logger.error(f"User growth stats failed: {str(e)}")
            return {}
