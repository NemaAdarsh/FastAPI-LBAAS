#!/usr/bin/env python3
"""
Comprehensive API Testing Script for FastAPI Load Balancer Service

This script tests all available API endpoints with proper authentication
and error handling.
"""

import requests
import json
import time
import websocket
from typing import Dict, Any, Optional
import argparse

class LBaaSAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.token = None
        self.headers = {"Content-Type": "application/json"}
        self.test_results = []
    
    def log_test(self, test_name: str, success: bool, response: Any = None, error: str = None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "timestamp": time.time()
        }
        if error:
            result["error"] = error
        if response and hasattr(response, 'status_code'):
            result["status_code"] = response.status_code
        
        self.test_results.append(result)
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
        if error:
            print(f"   Error: {error}")
    
    def make_request(self, method: str, endpoint: str, data: Dict = None, auth: bool = True) -> requests.Response:
        """Make HTTP request with proper headers"""
        url = f"{self.base_url}{endpoint}"
        headers = self.headers.copy()
        
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        try:
            if method.upper() == "GET":
                return requests.get(url, headers=headers)
            elif method.upper() == "POST":
                return requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                return requests.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                return requests.delete(url, headers=headers)
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")
    
    def test_health_endpoints(self):
        """Test health check endpoints"""
        print("\n🏥 Testing Health Endpoints...")
        
        # Basic health check
        try:
            response = self.make_request("GET", "/health/", auth=False)
            success = response.status_code == 200
            self.log_test("Health Check", success, response)
        except Exception as e:
            self.log_test("Health Check", False, error=str(e))
        
        # Detailed health check
        try:
            response = self.make_request("GET", "/health/detailed", auth=False)
            success = response.status_code == 200
            self.log_test("Detailed Health Check", success, response)
        except Exception as e:
            self.log_test("Detailed Health Check", False, error=str(e))
        
        # Readiness probe
        try:
            response = self.make_request("GET", "/health/readiness", auth=False)
            success = response.status_code in [200, 503]
            self.log_test("Readiness Probe", success, response)
        except Exception as e:
            self.log_test("Readiness Probe", False, error=str(e))
        
        # Liveness probe
        try:
            response = self.make_request("GET", "/health/liveness", auth=False)
            success = response.status_code == 200
            self.log_test("Liveness Probe", success, response)
        except Exception as e:
            self.log_test("Liveness Probe", False, error=str(e))
    
    def test_authentication(self, username: str = "admin", password: str = "admin123"):
        """Test authentication endpoints"""
        print("\n🔐 Testing Authentication...")
        
        # Test registration (if user doesn't exist)
        register_data = {
            "username": f"test_user_{int(time.time())}",
            "email": f"test_{int(time.time())}@example.com",
            "password": "testpass123",
            "role": "user"
        }
        
        try:
            response = self.make_request("POST", "/api/v1/auth/register", register_data, auth=False)
            success = response.status_code in [200, 201, 400]  # 400 might be "user exists"
            self.log_test("User Registration", success, response)
        except Exception as e:
            self.log_test("User Registration", False, error=str(e))
        
        # Test login
        login_data = {
            "username": username,
            "password": password
        }
        
        try:
            response = self.make_request("POST", "/api/v1/auth/login", login_data, auth=False)
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.log_test("User Login", True, response)
            else:
                self.log_test("User Login", False, response, "Login failed")
                return False
        except Exception as e:
            self.log_test("User Login", False, error=str(e))
            return False
        
        # Test get current user
        try:
            response = self.make_request("GET", "/api/v1/auth/me")
            success = response.status_code == 200
            self.log_test("Get Current User", success, response)
        except Exception as e:
            self.log_test("Get Current User", False, error=str(e))
        
        return True
    
    def test_tenant_endpoints(self):
        """Test tenant management endpoints"""
        print("\n🏢 Testing Tenant Management...")
        
        # Get current tenant info
        try:
            response = self.make_request("GET", "/api/v1/tenant/current/info")
            success = response.status_code in [200, 404]  # 404 if no tenant
            self.log_test("Get Current Tenant Info", success, response)
        except Exception as e:
            self.log_test("Get Current Tenant Info", False, error=str(e))
        
        # Get tenant usage
        try:
            response = self.make_request("GET", "/api/v1/tenant/current/usage")
            success = response.status_code in [200, 404]
            self.log_test("Get Tenant Usage", success, response)
        except Exception as e:
            self.log_test("Get Tenant Usage", False, error=str(e))
        
        # Get tenant limits
        try:
            response = self.make_request("GET", "/api/v1/tenant/current/limits")
            success = response.status_code in [200, 404]
            self.log_test("Get Tenant Limits", success, response)
        except Exception as e:
            self.log_test("Get Tenant Limits", False, error=str(e))
    
    def test_load_balancer_endpoints(self):
        """Test load balancer management endpoints"""
        print("\n⚖️ Testing Load Balancer Management...")
        
        lb_id = None
        
        # Create load balancer
        lb_data = {
            "name": f"test-lb-{int(time.time())}",
            "algorithm": "roundrobin",
            "port": 80,
            "ssl_enabled": False
        }
        
        try:
            response = self.make_request("POST", "/api/v1/loadbalancer/", lb_data)
            if response.status_code in [200, 201]:
                data = response.json()
                lb_id = data.get("id")
                self.log_test("Create Load Balancer", True, response)
            else:
                self.log_test("Create Load Balancer", False, response)
        except Exception as e:
            self.log_test("Create Load Balancer", False, error=str(e))
        
        # List load balancers
        try:
            response = self.make_request("GET", "/api/v1/loadbalancer/")
            success = response.status_code == 200
            self.log_test("List Load Balancers", success, response)
        except Exception as e:
            self.log_test("List Load Balancers", False, error=str(e))
        
        if lb_id:
            # Get specific load balancer
            try:
                response = self.make_request("GET", f"/api/v1/loadbalancer/{lb_id}")
                success = response.status_code == 200
                self.log_test("Get Load Balancer Details", success, response)
            except Exception as e:
                self.log_test("Get Load Balancer Details", False, error=str(e))
            
            # Test backend management
            self.test_backend_endpoints(lb_id)
            
            # Delete load balancer
            try:
                response = self.make_request("DELETE", f"/api/v1/loadbalancer/{lb_id}")
                success = response.status_code in [200, 204]
                self.log_test("Delete Load Balancer", success, response)
            except Exception as e:
                self.log_test("Delete Load Balancer", False, error=str(e))
    
    def test_backend_endpoints(self, lb_id: int):
        """Test backend server management"""
        print(f"\n🖥️ Testing Backend Management for LB {lb_id}...")
        
        backend_id = None
        
        # Add backend server
        backend_data = {
            "ip": "192.168.1.10",
            "port": 8080,
            "weight": 1,
            "max_conns": 100,
            "backup": False,
            "monitor": True
        }
        
        try:
            response = self.make_request("POST", f"/api/v1/loadbalancer/{lb_id}/backends", backend_data)
            if response.status_code in [200, 201]:
                data = response.json()
                backend_id = data.get("id")
                self.log_test("Add Backend Server", True, response)
            else:
                self.log_test("Add Backend Server", False, response)
        except Exception as e:
            self.log_test("Add Backend Server", False, error=str(e))
        
        # Get backend health
        try:
            response = self.make_request("GET", f"/api/v1/loadbalancer/{lb_id}/backends/health")
            success = response.status_code == 200
            self.log_test("Get Backend Health", success, response)
        except Exception as e:
            self.log_test("Get Backend Health", False, error=str(e))
        
        if backend_id:
            # Remove backend server
            try:
                response = self.make_request("DELETE", f"/api/v1/loadbalancer/{lb_id}/backends/{backend_id}")
                success = response.status_code in [200, 204]
                self.log_test("Remove Backend Server", success, response)
            except Exception as e:
                self.log_test("Remove Backend Server", False, error=str(e))
    
    def test_metrics_endpoints(self):
        """Test metrics and monitoring endpoints"""
        print("\n📊 Testing Metrics & Monitoring...")
        
        # Get tenant overview
        try:
            response = self.make_request("GET", "/api/v1/metrics/tenant/overview")
            success = response.status_code == 200
            self.log_test("Get Tenant Metrics Overview", success, response)
        except Exception as e:
            self.log_test("Get Tenant Metrics Overview", False, error=str(e))
        
        # Test with a mock load balancer ID
        test_lb_id = 1
        
        # Get load balancer metrics
        try:
            response = self.make_request("GET", f"/api/v1/metrics/load-balancer/{test_lb_id}?period=1h")
            success = response.status_code in [200, 404]  # 404 if LB doesn't exist
            self.log_test("Get Load Balancer Metrics", success, response)
        except Exception as e:
            self.log_test("Get Load Balancer Metrics", False, error=str(e))
        
        # Get backend metrics
        try:
            response = self.make_request("GET", f"/api/v1/metrics/load-balancer/{test_lb_id}/backends")
            success = response.status_code in [200, 404]
            self.log_test("Get Backend Metrics", success, response)
        except Exception as e:
            self.log_test("Get Backend Metrics", False, error=str(e))
        
        # Get alerts
        try:
            response = self.make_request("GET", f"/api/v1/metrics/alerts/{test_lb_id}")
            success = response.status_code in [200, 404]
            self.log_test("Get Load Balancer Alerts", success, response)
        except Exception as e:
            self.log_test("Get Load Balancer Alerts", False, error=str(e))
    
    def test_websocket_connection(self):
        """Test WebSocket connection for real-time metrics"""
        print("\n🔌 Testing WebSocket Connection...")
        
        try:
            ws_url = f"ws://localhost:8000/api/v1/loadbalancer/1/ws/metrics"
            ws = websocket.create_connection(ws_url, timeout=5)
            
            # Try to receive a message
            try:
                message = ws.recv()
                data = json.loads(message)
                ws.close()
                self.log_test("WebSocket Metrics Stream", True)
            except:
                ws.close()
                self.log_test("WebSocket Metrics Stream", False, error="No data received")
                
        except Exception as e:
            self.log_test("WebSocket Metrics Stream", False, error=str(e))
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("🧪 TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}")
                    if "error" in result:
                        print(f"    Error: {result['error']}")
        
        print("\n" + "="*60)
    
    def run_all_tests(self, username: str = "admin", password: str = "admin123"):
        """Run all API tests"""
        print("🚀 Starting FastAPI Load Balancer API Tests...")
        
        # Test health endpoints (no auth required)
        self.test_health_endpoints()
        
        # Test authentication and get token
        if self.test_authentication(username, password):
            # Run authenticated tests
            self.test_tenant_endpoints()
            self.test_load_balancer_endpoints()
            self.test_metrics_endpoints()
        else:
            print("❌ Authentication failed, skipping authenticated tests")
        
        # Test WebSocket (separate test)
        self.test_websocket_connection()
        
        # Print summary
        self.print_summary()

def main():
    parser = argparse.ArgumentParser(description="Test FastAPI Load Balancer API")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Base URL of the API (default: http://localhost:8000)")
    parser.add_argument("--username", default="admin", 
                       help="Username for authentication (default: admin)")
    parser.add_argument("--password", default="admin123", 
                       help="Password for authentication (default: admin123)")
    
    args = parser.parse_args()
    
    tester = LBaaSAPITester(args.url)
    tester.run_all_tests(args.username, args.password)

if __name__ == "__main__":
    main()
