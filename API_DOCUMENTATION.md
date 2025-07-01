# FastAPI Load Balancer Service - API Documentation

## Overview
This FastAPI application provides a comprehensive Load Balancer as a Service (LBaaS) platform with multi-tenancy, authentication, metrics, and health monitoring.

## Base URL
- Development: `http://localhost:8000`
- Production: `https://your-domain.com`

## Authentication
Most endpoints require authentication using Bearer tokens. Include the token in the Authorization header:
```
Authorization: Bearer <your_access_token>
```

## API Endpoints

### Health & Status
- `GET /health/` - Basic health check
- `GET /health/detailed` - Detailed health check with service status
- `GET /health/readiness` - Kubernetes readiness probe
- `GET /health/liveness` - Kubernetes liveness probe
- `GET /health/system` - System metrics and resource usage

### Authentication
- `POST /api/v1/auth/login` - User login (returns JWT token)
- `POST /api/v1/auth/token` - OAuth2 compatible login
- `POST /api/v1/auth/register` - Register new user
- `GET /api/v1/auth/me` - Get current user info
- `PUT /api/v1/auth/me` - Update current user info
- `POST /api/v1/auth/change-password` - Change password
- `POST /api/v1/auth/logout` - Logout user
- `GET /api/v1/auth/users` - List all users (admin only)
- `GET /api/v1/auth/users/{user_id}` - Get user by ID (admin only)
- `PUT /api/v1/auth/users/{user_id}` - Update user (admin only)
- `DELETE /api/v1/auth/users/{user_id}` - Delete user (admin only)

### Tenant Management
- `POST /api/v1/tenant/` - Create tenant (admin only)
- `GET /api/v1/tenant/` - List all tenants (admin only)
- `GET /api/v1/tenant/{tenant_id}` - Get tenant by ID (admin only)
- `PUT /api/v1/tenant/{tenant_id}` - Update tenant (admin only)
- `DELETE /api/v1/tenant/{tenant_id}` - Delete tenant (admin only)
- `GET /api/v1/tenant/current/info` - Get current tenant info
- `GET /api/v1/tenant/current/usage` - Get current tenant usage
- `GET /api/v1/tenant/current/limits` - Get current tenant limits
- `PUT /api/v1/tenant/current/info` - Update current tenant
- `GET /api/v1/tenant/{tenant_id}/users` - Get tenant users (admin only)
- `GET /api/v1/tenant/{tenant_id}/load-balancers` - Get tenant load balancers (admin only)

### Load Balancer Management
- `POST /api/v1/loadbalancer/` - Create load balancer
- `GET /api/v1/loadbalancer/` - List load balancers (tenant-scoped)
- `GET /api/v1/loadbalancer/{lb_id}` - Get load balancer details
- `PUT /api/v1/loadbalancer/{lb_id}` - Update load balancer
- `DELETE /api/v1/loadbalancer/{lb_id}` - Delete load balancer
- `GET /api/v1/loadbalancer/health` - Service health check

### Backend Server Management
- `POST /api/v1/loadbalancer/{lb_id}/backends` - Add backend server
- `GET /api/v1/loadbalancer/{lb_id}/backends` - List backend servers
- `PUT /api/v1/loadbalancer/{lb_id}/backends/{backend_id}` - Update backend
- `DELETE /api/v1/loadbalancer/{lb_id}/backends/{backend_id}` - Remove backend
- `GET /api/v1/loadbalancer/{lb_id}/backends/health` - Get backend health status

### Metrics & Monitoring
- `GET /api/v1/metrics/load-balancer/{lb_id}` - Get LB metrics
- `GET /api/v1/metrics/load-balancer/{lb_id}/backends` - Get backend metrics
- `GET /api/v1/metrics/load-balancer/{lb_id}/backend/{backend_id}` - Get single backend metrics
- `GET /api/v1/metrics/system` - Get system metrics (admin only)
- `GET /api/v1/metrics/tenant/overview` - Get tenant metrics overview
- `POST /api/v1/metrics/refresh/{lb_id}` - Refresh metrics for LB
- `GET /api/v1/metrics/alerts/{lb_id}` - Get alerts for LB

### Audit & Logs
- `GET /api/v1/metrics/audit/logs` - Get audit logs (admin only)

### WebSocket Endpoints
- `WS /api/v1/loadbalancer/{lb_id}/ws/metrics` - Real-time metrics stream

## Request/Response Examples

### Create Load Balancer
```bash
POST /api/v1/loadbalancer/
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "web-app-lb",
  "algorithm": "roundrobin",
  "port": 80,
  "ssl_enabled": false
}
```

### Add Backend Server
```bash
POST /api/v1/loadbalancer/1/backends
Content-Type: application/json
Authorization: Bearer <token>

{
  "ip": "192.168.1.10",
  "port": 8080,
  "weight": 1,
  "max_conns": 100,
  "backup": false,
  "monitor": true
}
```

### Get Load Balancer Metrics
```bash
GET /api/v1/metrics/load-balancer/1?period=1h
Authorization: Bearer <token>
```

### User Login
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "secure_password"
}
```

## Query Parameters

### Metrics Endpoints
- `period`: Time period for metrics (`5m`, `15m`, `1h`, `6h`, `24h`, `7d`)

### Pagination
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 50, max: 500)
- `skip`: Number of items to skip
- `limit`: Maximum number of items to return

### Filtering
- `active_only`: Filter by active items only
- `action`: Filter audit logs by action type
- `resource`: Filter audit logs by resource type
- `start_date`: Filter from date (ISO format)
- `end_date`: Filter to date (ISO format)

## Error Responses

All endpoints return structured error responses:

```json
{
  "detail": "Error message",
  "request_id": "uuid"
}
```

### Common HTTP Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `429` - Rate Limited
- `500` - Internal Server Error

## Rate Limiting
API endpoints are rate limited to 100 requests per minute per user/IP.

## WebSocket Usage

Connect to real-time metrics:
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/loadbalancer/1/ws/metrics');
ws.onmessage = (event) => {
  const metrics = JSON.parse(event.data);
  console.log(metrics);
};
```

## Authentication Flow

1. Register or obtain credentials
2. Login to get JWT token
3. Include token in Authorization header for protected endpoints
4. Token expires after configured time (default: 60 minutes)

## Multi-Tenancy

- Each user belongs to a tenant
- Resources are isolated by tenant
- Users can only access resources in their tenant
- Admins can access all tenants

## Subscription Tiers

### Free Tier
- 5 load balancers
- 3 backends per LB
- 2 users
- Basic monitoring

### Pro Tier  
- 25 load balancers
- 10 backends per LB
- 10 users
- SSL support
- Advanced monitoring

### Enterprise Tier
- 100 load balancers
- 50 backends per LB
- 50 users
- Full feature set
- Priority support

## Environment Variables

- `DATABASE_URL` - Database connection string
- `SECRET_KEY` - JWT secret key
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration time
- `REDIS_URL` - Redis connection for caching
- `ENV` - Environment (development/production)
- `DEBUG` - Debug mode (true/false)

## Development

Start the development server:
```bash
uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

Access the interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
