import os
import subprocess
from jinja2 import Template
from typing import List
from models.load_balancer import LoadBalancer

class LoadBalancerManager:
    def __init__(self):
        self.config_path = os.getenv("HAPROXY_CONFIG_PATH", "/etc/haproxy/haproxy.cfg")
        self.config_template = self._get_haproxy_template()
    
    def _get_haproxy_template(self) -> Template:
        template_str = """
global
    daemon
    stats socket /var/run/haproxy.sock mode 660 level admin

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s

{% for lb in load_balancers %}
frontend {{ lb.name }}_frontend
    bind *:{{ lb.frontend_port }}
    default_backend {{ lb.name }}_backend

backend {{ lb.name }}_backend
    balance {{ lb.algorithm.value }}
    {% for server in lb.backend_servers %}
    {% if server.is_healthy %}
    server {{ server.host }}_{{ server.port }} {{ server.host }}:{{ server.port }} check weight {{ server.weight }}
    {% endif %}
    {% endfor %}

{% endfor %}
"""
        return Template(template_str)
    
    async def create_lb_config(self, load_balancer: LoadBalancer):
        """Create HAProxy configuration for a new load balancer"""
        await self._regenerate_config()
    
    async def update_lb_config(self, load_balancer: LoadBalancer):
        """Update HAProxy configuration for an existing load balancer"""
        await self._regenerate_config()
    
    async def delete_lb_config(self, load_balancer: LoadBalancer):
        """Remove load balancer from HAProxy configuration"""
        await self._regenerate_config()
    
    async def _regenerate_config(self):
        """Regenerate the entire HAProxy configuration"""
        # This would fetch all active load balancers from database
        # and regenerate the config file
        # For now, this is a placeholder
        pass
    
    async def reload_haproxy(self):
        """Reload HAProxy with new configuration"""
        try:
            subprocess.run(["haproxy", "-f", self.config_path, "-c"], check=True)
            subprocess.run(["systemctl", "reload", "haproxy"], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to reload HAProxy: {e}")