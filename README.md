# LBaaS - Load Balancer as a Service

A comprehensive Load Balancer as a Service platform built with FastAPI that provides dynamic load balancing capabilities using HAProxy. This service allows users to create, manage, and monitor load balancers through a RESTful API.

## 🚀 Features

- **Dynamic Load Balancer Creation**: Create and configure load balancers on-demand
- **Multiple Load Balancing Algorithms**: Round Robin, Least Connections, IP Hash, Weighted Round Robin
- **Backend Server Management**: Add, remove, and monitor backend servers
- **Health Monitoring**: Automatic health checks for backend servers
- **Real-time Configuration**: Dynamic HAProxy configuration updates without service interruption
- **REST API**: Complete API for programmatic management
- **Web Dashboard**: Interactive web interface for monitoring and management
- **Metrics & Monitoring**: Built-in statistics and monitoring endpoints

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Load Balancer Engine**: HAProxy
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Configuration Management**: Dynamic HAProxy config generation
- **API Documentation**: Automatic OpenAPI/Swagger documentation

## 📁 Project Structure

```
fastapi-app/
├── src/
│   ├── app.py                  # FastAPI application entry point
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py         # Database configuration
│   │   └── load_balancer.py    # Data models for LB and servers
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py           # Health check endpoints
│   │   └── load_balancer.py    # Load balancer management API
│   └── utils/
│       ├── __init__.py
│       ├── schemas.py          # Pydantic models for API
│       └── lb_manager.py       # HAProxy configuration manager
├── requirements.txt            # Python dependencies
├── .env                       # Environment variables
├── docker-compose.yml         # Docker services configuration
├── Dockerfile                 # Application container
└── README.md                  # Project documentation
```

## 🔧 Setup Instructions

### Prerequisites

- Python 3.8+
- PostgreSQL
- HAProxy
- Docker (optional)

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd fastapi-app
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up environment variables:**
   Create a `.env` file in the root directory:
   ```env
   DATABASE_URL=postgresql://username:password@localhost:5432/lbaas_db
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   HAPROXY_CONFIG_PATH=/etc/haproxy/haproxy.cfg
   HAPROXY_STATS_URL=http://localhost:8404/stats
   ```

6. **Set up PostgreSQL database:**
   ```bash
   # Create database
   createdb lbaas_db
   
   # Run migrations (if using Alembic)
   alembic upgrade head
   ```

7. **Run the application:**
   ```bash
   uvicorn src.app:app --reload
   ```

### Docker Setup

1. **Using Docker Compose:**
   ```bash
   docker-compose up -d
   ```

## 📖 API Usage

### Start the server
```bash
uvicorn src.app:app --reload
```

### Access the API
- **API Documentation**: `http://127.0.0.1:8000/docs`
- **Alternative Docs**: `http://127.0.0.1:8000/redoc`
- **HAProxy Stats**: `http://127.0.0.1:8404/stats`

### Example API Calls

**Create a Load Balancer:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/loadbalancer/" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "web-lb",
       "frontend_port": 80,
       "algorithm": "roundrobin"
     }'
```

**Add Backend Servers:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/loadbalancer/1/backends" \
     -H "Content-Type: application/json" \
     -d '{
       "host": "192.168.1.10",
       "port": 8080,
       "weight": 1
     }'
```

**List Load Balancers:**
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/loadbalancer/"
```

## 🔍 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health/` | Health check |
| GET | `/health/ready` | Readiness check |
| POST | `/api/v1/loadbalancer/` | Create load balancer |
| GET | `/api/v1/loadbalancer/` | List all load balancers |
| GET | `/api/v1/loadbalancer/{id}` | Get specific load balancer |
| POST | `/api/v1/loadbalancer/{id}/backends` | Add backend server |
| DELETE | `/api/v1/loadbalancer/{id}` | Delete load balancer |

## 🏗️ Load Balancing Algorithms

- **Round Robin**: Distributes requests evenly across all servers
- **Least Connections**: Routes to server with fewest active connections
- **IP Hash**: Routes based on client IP hash (session persistence)
- **Weighted Round Robin**: Round robin with server weight consideration

## 📊 Monitoring

- HAProxy built-in statistics dashboard
- Health check monitoring for backend servers
- API endpoints for retrieving load balancer metrics
- Integration ready for Prometheus and Grafana

## 🚀 Deployment

### Production Considerations

1. **Database**: Use managed PostgreSQL service
2. **Load Balancer**: Deploy HAProxy on dedicated instances
3. **Security**: Implement authentication and authorization
4. **Monitoring**: Set up comprehensive logging and monitoring
5. **High Availability**: Deploy multiple API instances behind a load balancer

### Container Deployment

```bash
# Build the image
docker build -t lbaas-api .

# Run with docker-compose
docker-compose up -d
```

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License. See the LICENSE file for details.

## 🔗 Related Projects

- [HAProxy Documentation](http://www.haproxy.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)