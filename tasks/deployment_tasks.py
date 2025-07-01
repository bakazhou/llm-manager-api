import logging
import time
from datetime import datetime, timedelta

from api.models.deployment import Deployment
from api.models.model import db
from api.services.deployment_service import DeploymentService
from api.services.system_service import SystemService
from . import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, name='deployment.health_check')
def health_check_task(self, deployment_id):
    """Health check task"""
    try:
        logger.info(f"Starting health check: {deployment_id}")

        deployment_service = DeploymentService()
        result = deployment_service.check_deployment_health(deployment_id)

        logger.info(f"Health check completed: {deployment_id}, result: {result.get('healthy', False)}")
        return result

    except Exception as e:
        logger.error(f"Health check task failed: {str(e)}")
        self.retry(countdown=60, max_retries=3)


@celery.task(bind=True, name='deployment.auto_deploy')
def auto_deploy_task(self, model_id, source, name, config=None):
    """Auto deployment task"""
    try:
        logger.info(f"Starting auto deployment: {model_id}")

        # Update task status
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Creating deployment configuration', 'progress': 10}
        )

        deployment_service = DeploymentService()

        # Create deployment
        deployment = deployment_service.create_deployment(model_id, source, name, config)

        self.update_state(
            state='PROGRESS',
            meta={'status': 'Starting deployment service', 'progress': 50}
        )

        # Start deployment
        result = deployment_service.start_deployment(deployment.id)

        self.update_state(
            state='PROGRESS',
            meta={'status': 'Verifying deployment status', 'progress': 80}
        )

        # Wait for service to start
        time.sleep(10)

        # Check health status
        health_result = deployment_service.check_deployment_health(deployment.id)

        if health_result.get('healthy'):
            logger.info(f"Auto deployment successful: {deployment.id}")
            return {
                'deployment_id': deployment.id,
                'status': 'success',
                'message': 'Deployment successful',
                'url': deployment.get_service_url(),
                'health': health_result
            }
        else:
            logger.warning(f"Deployment started but health check failed: {deployment.id}")
            return {
                'deployment_id': deployment.id,
                'status': 'warning',
                'message': 'Deployment started but health check failed',
                'health': health_result
            }

    except Exception as e:
        logger.error(f"Auto deployment task failed: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e)
        }


@celery.task(bind=True, name='deployment.batch_health_check')
def batch_health_check_task(self):
    """Batch health check task"""
    try:
        logger.info("Starting batch health check")

        # Get all running deployments
        active_deployments = Deployment.get_active_deployments()

        results = []
        deployment_service = DeploymentService()

        for deployment in active_deployments:
            try:
                result = deployment_service.check_deployment_health(deployment.id)
                results.append({
                    'deployment_id': deployment.id,
                    'name': deployment.name,
                    'healthy': result.get('healthy', False),
                    'status': result.get('status', 'unknown')
                })
            except Exception as e:
                logger.error(f"Health check failed {deployment.id}: {str(e)}")
                results.append({
                    'deployment_id': deployment.id,
                    'name': deployment.name,
                    'healthy': False,
                    'error': str(e)
                })

        # Calculate results
        total = len(results)
        healthy_count = sum(1 for r in results if r.get('healthy'))
        unhealthy_count = total - healthy_count

        summary = {
            'total': total,
            'healthy': healthy_count,
            'unhealthy': unhealthy_count,
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(f"Batch health check completed: {healthy_count}/{total} healthy")
        return summary

    except Exception as e:
        logger.error(f"Batch health check task failed: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@celery.task(bind=True, name='deployment.cleanup_failed')
def cleanup_failed_deployments_task(self):
    """Cleanup failed deployments"""
    try:
        logger.info("Starting cleanup of failed deployments")

        # Find deployments that failed more than 1 hour ago
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        failed_deployments = Deployment.query.filter(
            Deployment.status == 'failed',
            Deployment.updated_at < cutoff_time
        ).all()

        cleaned_count = 0
        deployment_service = DeploymentService()

        for deployment in failed_deployments:
            try:
                # Clean up resources
                if deployment.container_id:
                    deployment_service._stop_container(deployment.container_id)

                # Delete deployment record
                db.session.delete(deployment)
                cleaned_count += 1

                logger.info(f"Cleaned up failed deployment: {deployment.id}")

            except Exception as e:
                logger.error(f"Failed to cleanup deployment {deployment.id}: {str(e)}")

        if cleaned_count > 0:
            db.session.commit()

        logger.info(f"Cleanup completed, cleaned {cleaned_count} failed deployments")
        return {
            'cleaned_count': cleaned_count,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Cleanup failed deployments task failed: {str(e)}")
        db.session.rollback()
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@celery.task(bind=True, name='deployment.resource_monitor')
def resource_monitor_task(self):
    """Resource monitoring task"""
    try:
        logger.info("Starting resource monitoring")

        system_service = SystemService()

        # Get system resource information
        resources = system_service.get_system_resources()
        load_info = system_service.get_system_load()
        health_info = system_service.check_system_health()

        # Check if alerts are needed
        alerts = []

        # CPU alert
        if load_info.get('cpu_percent', 0) > 90:
            alerts.append({
                'type': 'cpu_high',
                'message': f"CPU usage too high: {load_info['cpu_percent']}%",
                'severity': 'critical'
            })

        # Memory alert
        if load_info.get('memory_percent', 0) > 90:
            alerts.append({
                'type': 'memory_high',
                'message': f"Memory usage too high: {load_info['memory_percent']}%",
                'severity': 'critical'
            })

        # Disk alert
        disk_percent = resources.get('disk', {}).get('percent', 0)
        if disk_percent > 90:
            alerts.append({
                'type': 'disk_high',
                'message': f"Disk usage too high: {disk_percent:.1f}%",
                'severity': 'critical'
            })

        # If there are alerts, log them
        if alerts:
            for alert in alerts:
                logger.warning(f"System alert: {alert['message']}")

        monitor_result = {
            'resources': resources,
            'load': load_info,
            'health': health_info,
            'alerts': alerts,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(f"Resource monitoring completed, load level: {load_info.get('load_level', 'unknown')}")
        return monitor_result

    except Exception as e:
        logger.error(f"Resource monitoring task failed: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


@celery.task(bind=True, name='deployment.restart_unhealthy')
def restart_unhealthy_deployments_task(self):
    """Restart unhealthy deployments"""
    try:
        logger.info("Starting check and restart unhealthy deployments")

        # Get all running deployments
        active_deployments = Deployment.query.filter(
            Deployment.status == 'running'
        ).all()

        restarted_count = 0
        deployment_service = DeploymentService()

        for deployment in active_deployments:
            try:
                # Check health status
                health_result = deployment_service.check_deployment_health(deployment.id)

                if not health_result.get('healthy'):
                    logger.warning(f"Found unhealthy deployment: {deployment.id}, attempting restart")

                    # Restart deployment
                    restart_result = deployment_service.restart_deployment(deployment.id)

                    if restart_result:
                        restarted_count += 1
                        logger.info(f"Deployment restart successful: {deployment.id}")
                    else:
                        logger.error(f"Deployment restart failed: {deployment.id}")

            except Exception as e:
                logger.error(f"Check/restart deployment failed {deployment.id}: {str(e)}")

        logger.info(f"Restart unhealthy deployments completed, restarted {restarted_count} deployments")
        return {
            'restarted_count': restarted_count,
            'timestamp': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Restart unhealthy deployments task failed: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
