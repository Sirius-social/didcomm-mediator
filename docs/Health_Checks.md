# Availability and scaling. Http paths for checking readiness and liveness.

We offer to use next URLs for checking health of the service
  - ```/maintenance/health_check``` will return 2xx Http status if web server is reachable. You may put
    this path into docker-based cluster orchestrator like Kubernetes to check service can response to requests to 
    manage traffic across instances (ex: Kubernetes Pods)
  - ```/maintenance/liveness_check``` will return 2xx Http status if application is configured and all 
    dependency services are reachable and successfully configured. You may put this path
    into orchestrator like Kubernetes to check running container is live. This handler will check dependency services
    are running successfully.
  
## Scaling and dependencies:
  - **Postgres**: persistence component, application don't route read sql queries to replicas. To avoid
  this restriction use tools like [Pgpool-II](https://www.pgpool.net/mediawiki/index.php/Main_Page)
  - **Memcached**: caching component. To make **memcached** high-available you may deploy it to Cluster
    as service or use  alternate approaches like [this](https://programmer.group/high-availability-ha-architecture-for-memcached-cluster.html)
  - **Redis**: Use HA Redis cluster or deploy multiple redis instances as separate services (with scale **replicas = 1**)
  in a cluster (cluster orchestrator will schedule instances for HA purposes).