#!/usr/bin/env python3
"""
OpenShift Cluster Monitor
Monitoreo continuo de clusters OpenShift usando comandos oc
"""

import os
import json
import time
import logging
import requests
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import schedule
import asyncio
import threading
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
import yaml

# Importar el bot de Telegram
from telegram_bot import OpenShiftTelegramBot

# Suprimir warnings de SSL para desarrollo
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

console = Console()

@dataclass
class ClusterConfig:
    """Configuración de un cluster individual"""
    name: str
    api_url: str
    token: str

@dataclass
class NamespaceStatus:
    """Estado de un namespace específico"""
    name: str
    status: str  # Active, Terminating, etc.
    pods_count: int
    pods_running: int
    pods_failed: int
    pods_pending: int
    services_count: int
    deployments_count: int
    critical_pods: List[str]  # Pods con problemas
    resource_usage: Dict[str, float]  # CPU, memoria por namespace

@dataclass
class PodStatus:
    """Estado de un pod específico"""
    name: str
    namespace: str
    status: str  # Running, Failed, Pending, etc.
    ready: str  # 1/1, 0/1, etc.
    restart_count: int
    age: str
    ip: str
    node: str
    resource_usage: Dict[str, float]  # CPU, memoria actual

@dataclass
class ClusterStatus:
    """Estado actual de un cluster"""
    name: str
    timestamp: datetime
    operators_status: Dict[str, str]
    nodes_status: Dict[str, bool]
    resource_metrics: Dict[str, Dict[str, float]]
    overall_health: str
    critical_issues: List[str]
    namespaces_status: Dict[str, NamespaceStatus]  # Nuevo: estado de namespaces
    pods_summary: Dict[str, int]  # Resumen de pods por estado

class OpenShiftMonitor:
    """Monitor principal para clusters OpenShift"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or 'env.example'
        self.clusters: List[ClusterConfig] = []
        self.cluster_statuses: Dict[str, ClusterStatus] = {}
        self.previous_statuses: Dict[str, ClusterStatus] = {}
        self.telegram_bot = None
        self.load_config()
        self.setup_telegram_bot()
        
    def load_config(self):
        """Cargar configuración desde archivo .env o variables de entorno"""
        try:
            # Cargar desde archivo .env si existe
            if os.path.exists('.env'):
                from dotenv import load_dotenv
                load_dotenv('.env')
            
            # Obtener configuración de clusters
            api_urls = os.getenv('OPENSHIFT_API_URLS', '').split(',')
            tokens = os.getenv('OPENSHIFT_TOKENS', '').split(',')
            cluster_names = os.getenv('CLUSTER_NAMES', '').split(',')
            
            # Validar que tengamos la misma cantidad de configuraciones
            if not all([api_urls, tokens, cluster_names]):
                raise ValueError("Faltan configuraciones de cluster")
            
            # Crear configuraciones de cluster
            for i, name in enumerate(cluster_names):
                if i < len(api_urls) and i < len(tokens):
                    cluster_config = ClusterConfig(
                        name=name.strip(),
                        api_url=api_urls[i].strip(),
                        token=tokens[i].strip()
                    )
                    self.clusters.append(cluster_config)
                    logger.info(f"Cluster configurado: {name}")
            
            if not self.clusters:
                raise ValueError("No se pudo configurar ningún cluster")
                
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            raise
    
    def setup_telegram_bot(self):
        """Configurar bot de Telegram si está habilitado"""
        try:
            telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if telegram_token:
                # Obtener usuarios autorizados del archivo de configuración
                authorized_users = []
                try:
                    auth_users_str = os.getenv('TELEGRAM_AUTHORIZED_USERS', '')
                    if auth_users_str:
                        authorized_users = [int(uid.strip()) for uid in auth_users_str.split(',') if uid.strip().isdigit()]
                except Exception as e:
                    logger.warning(f"No se pudieron parsear usuarios autorizados: {e}")
                    authorized_users = []
                
                self.telegram_bot = OpenShiftTelegramBot(telegram_token, authorized_users, self)
                logger.info("Bot de Telegram configurado")
                
                # Iniciar bot en un hilo separado
                bot_thread = threading.Thread(target=self.run_telegram_bot, daemon=True)
                bot_thread.start()
                logger.info("Bot de Telegram iniciado en hilo separado")
            else:
                logger.info("Bot de Telegram no configurado (TELEGRAM_BOT_TOKEN no definido)")
        except Exception as e:
            logger.error(f"Error configurando bot de Telegram: {e}")
    
    def run_telegram_bot(self):
        """Ejecutar bot de Telegram en hilo separado"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.telegram_bot.start_bot())
            loop.run_forever()
        except Exception as e:
            logger.error(f"Error ejecutando bot de Telegram: {e}")
    
    def execute_openshift_api_call(self, cluster: ClusterConfig, endpoint: str, method: str = 'GET') -> Dict:
        """Ejecutar llamada a la API de OpenShift"""
        try:
            headers = {
                'Authorization': f'Bearer {cluster.token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            url = f"{cluster.api_url}{endpoint}"
            
            if method == 'GET':
                response = requests.get(url, headers=headers, verify=False, timeout=30)
            else:
                response = requests.post(url, headers=headers, verify=False, timeout=30)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'status_code': response.status_code
                }
            else:
                logger.error(f"API call failed for {cluster.name}: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'error': response.text
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling OpenShift API for {cluster.name}")
            return {'success': False, 'error': 'Timeout'}
        except Exception as e:
            logger.error(f"Error calling OpenShift API for {cluster.name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_openshift_api_connection(self, cluster: ClusterConfig) -> bool:
        """Probar conectividad con la API de OpenShift"""
        try:
            result = self.execute_openshift_api_call(cluster, '/apis/user.openshift.io/v1/users/~')
            if result['success']:
                user_info = result['data']
                username = user_info.get('metadata', {}).get('name', 'unknown')
                logger.info(f"Conexión exitosa con OpenShift API en {cluster.name}: usuario {username}")
                return True
            else:
                logger.error(f"Error de conectividad con OpenShift API en {cluster.name}: {result.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            logger.error(f"Error probando conectividad con OpenShift API en {cluster.name}: {e}")
            return False
    
    def handle_auth_error(self, cluster: ClusterConfig, error: Exception) -> None:
        """Manejar errores de autenticación específicamente"""
        error_str = str(error)
        if "401" in error_str or "Unauthorized" in error_str:
            logger.error(f"Error de autenticación en {cluster.name}: Token inválido o expirado")
            logger.info(f"Verifica que el token para {cluster.name} sea válido con: oc whoami -t")
        elif "403" in error_str or "Forbidden" in error_str:
            logger.error(f"Error de permisos en {cluster.name}: Token no tiene permisos suficientes")
        elif "SSL" in error_str or "certificate" in error_str:
            logger.warning(f"Advertencia SSL en {cluster.name}: Usando conexión no verificada")
        else:
            logger.error(f"Error desconocido en {cluster.name}: {error}")
    
    def check_cluster_operators(self, cluster: ClusterConfig) -> Dict[str, str]:
        """Verificar estado de operadores del cluster usando OpenShift API"""
        try:
            result = self.execute_openshift_api_call(cluster, '/apis/config.openshift.io/v1/clusteroperators')
            if not result['success']:
                return {}
            
            operators_data = result['data']
            operators_status = {}
            
            for operator in operators_data.get('items', []):
                name = operator['metadata']['name']
                conditions = operator.get('status', {}).get('conditions', [])
                
                # Buscar condición de degradado
                degraded = False
                for condition in conditions:
                    if condition['type'] == 'Degraded' and condition['status'] == 'True':
                        degraded = True
                        break
                
                operators_status[name] = 'Degraded' if degraded else 'OK'
            
            return operators_status
            
        except Exception as e:
            logger.error(f"Error verificando operadores de {cluster.name}: {e}")
            return {}
    
    def check_nodes_status(self, cluster: ClusterConfig) -> Dict[str, bool]:
        """Verificar estado de nodos usando OpenShift API"""
        try:
            result = self.execute_openshift_api_call(cluster, '/api/v1/nodes')
            if not result['success']:
                return {}
            
            nodes_data = result['data']
            nodes_status = {}
            
            for node in nodes_data.get('items', []):
                name = node['metadata']['name']
                conditions = node.get('status', {}).get('conditions', [])
                
                # Verificar si el nodo está Ready
                is_ready = False
                for condition in conditions:
                    if condition['type'] == 'Ready' and condition['status'] == 'True':
                        is_ready = True
                        break
                
                nodes_status[name] = is_ready
            
            return nodes_status
            
        except Exception as e:
            logger.error(f"Error verificando nodos de {cluster.name}: {e}")
            return {}
    
    def get_resource_metrics(self, cluster: ClusterConfig) -> Dict[str, Dict[str, float]]:
        """Obtener métricas de recursos usando OpenShift API"""
        try:
            result = self.execute_openshift_api_call(cluster, '/api/v1/nodes')
            if not result['success']:
                logger.warning(f"No se pudieron obtener métricas de {cluster.name}: {result.get('error', 'Unknown error')}")
                return {}
            
            nodes_data = result['data']
            metrics = {}
            
            logger.info(f"Procesando métricas para {len(nodes_data.get('items', []))} nodos en {cluster.name}")
            
            for node in nodes_data.get('items', []):
                name = node['metadata']['name']
                capacity = node.get('status', {}).get('capacity', {})
                allocatable = node.get('status', {}).get('allocatable', {})
                
                logger.debug(f"Nodo {name}: capacity={capacity}, allocatable={allocatable}")
                
                # Calcular porcentajes de uso
                node_metrics = {}
                
                # CPU
                if 'cpu' in capacity and 'cpu' in allocatable:
                    cpu_capacity = self.parse_cpu(capacity['cpu'])
                    cpu_allocatable = self.parse_cpu(allocatable['cpu'])
                    if cpu_capacity > 0:
                        # CPU en uso = (capacidad - allocatable) / capacidad * 100
                        cpu_usage = ((cpu_capacity - cpu_allocatable) / cpu_capacity) * 100
                        node_metrics['cpu'] = min(max(cpu_usage, 0.0), 100.0)  # Entre 0 y 100
                        logger.debug(f"CPU {name}: capacity={cpu_capacity}, allocatable={cpu_allocatable}, usage={node_metrics['cpu']:.1f}%")
                
                # Memoria
                if 'memory' in capacity and 'memory' in allocatable:
                    mem_capacity = self.parse_memory(capacity['memory'])
                    mem_allocatable = self.parse_memory(allocatable['memory'])
                    if mem_capacity > 0:
                        # Memoria en uso = (capacidad - allocatable) / capacidad * 100
                        mem_usage = ((mem_capacity - mem_allocatable) / mem_capacity) * 100
                        node_metrics['memory'] = min(max(mem_usage, 0.0), 100.0)  # Entre 0 y 100
                        logger.debug(f"Memory {name}: capacity={mem_capacity}, allocatable={mem_allocatable}, usage={node_metrics['memory']:.1f}%")
                
                if node_metrics:
                    metrics[name] = node_metrics
                    logger.info(f"Métricas calculadas para {name}: {node_metrics}")
            
            logger.info(f"Métricas obtenidas para {cluster.name}: {len(metrics)} nodos con datos")
            return metrics
            
        except Exception as e:
            logger.error(f"Error obteniendo métricas de {cluster.name}: {e}")
            return {}
    
    def parse_memory(self, memory_str: str) -> float:
        """Parsear string de memoria a bytes (decimal)"""
        try:
            if memory_str.endswith('Ki'):
                return float(memory_str[:-2]) * 1024
            elif memory_str.endswith('Mi'):
                return float(memory_str[:-2]) * 1024 * 1024
            elif memory_str.endswith('Gi'):
                return float(memory_str[:-2]) * 1024 * 1024 * 1024
            else:
                return float(memory_str)
        except:
            return 0.0
    
    def parse_cpu(self, cpu_str: str) -> float:
        """Parsear string de CPU a cores (puede ser decimal)"""
        try:
            if cpu_str.endswith('m'):
                # Convertir millicores a cores (ej: "15500m" -> 15.5)
                millicores = int(cpu_str[:-1])
                return millicores / 1000.0
            else:
                return float(cpu_str)
        except:
            return 1.0

    def get_namespaces_status(self, cluster: ClusterConfig) -> Dict[str, NamespaceStatus]:
        """Obtener estado de todos los namespaces del cluster usando la API"""
        try:
            # Usar la API de OpenShift en lugar de comandos oc
            result = self.execute_openshift_api_call(cluster, '/api/v1/namespaces')
            if not result['success']:
                logger.warning(f"No se pudieron obtener namespaces: {result.get('error', 'Unknown error')}")
                return {}
            
            namespaces_data = result['data']
            namespaces = {}
            
            for namespace in namespaces_data.get('items', []):
                name = namespace['metadata']['name']
                status = namespace['status']['phase']
                
                # Obtener información detallada del namespace usando la API
                namespace_status = self.get_namespace_details_via_api(cluster, name)
                namespaces[name] = namespace_status
            
            logger.info(f"Obtenidos {len(namespaces)} namespaces para {cluster.name}")
            return namespaces
            
        except Exception as e:
            logger.error(f"Error obteniendo namespaces: {e}")
            return {}

    def get_namespace_details_via_api(self, cluster: ClusterConfig, namespace: str) -> NamespaceStatus:
        """Obtener detalles específicos de un namespace usando la API"""
        try:
            # Obtener pods del namespace
            pods_result = self.execute_openshift_api_call(cluster, f'/api/v1/namespaces/{namespace}/pods')
            
            # Obtener servicios del namespace
            services_result = self.execute_openshift_api_call(cluster, f'/api/v1/namespaces/{namespace}/services')
            
            # Obtener deployments del namespace
            deployments_result = self.execute_openshift_api_call(cluster, f'/apis/apps/v1/namespaces/{namespace}/deployments')
            
            # Procesar pods
            pods_count = 0
            pods_running = 0
            pods_failed = 0
            pods_pending = 0
            critical_pods = []
            
            if pods_result['success']:
                pods_data = pods_result['data']
                for pod in pods_data.get('items', []):
                    pods_count += 1
                    status = pod['status']['phase']
                    pod_name = pod['metadata']['name']
                    
                    if status == 'Running':
                        pods_running += 1
                    elif status == 'Failed':
                        pods_failed += 1
                        critical_pods.append(pod_name)
                    elif status == 'Pending':
                        pods_pending += 1
                        critical_pods.append(pod_name)
            
            # Contar servicios y deployments
            services_count = len(services_result['data'].get('items', [])) if services_result['success'] else 0
            deployments_count = len(deployments_result['data'].get('items', [])) if deployments_result['success'] else 0
            
            return NamespaceStatus(
                name=namespace,
                status="Active",  # Por defecto
                pods_count=pods_count,
                pods_running=pods_running,
                pods_failed=pods_failed,
                pods_pending=pods_pending,
                services_count=services_count,
                deployments_count=deployments_count,
                critical_pods=critical_pods,
                resource_usage={}  # Se puede expandir con métricas de Prometheus
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo detalles del namespace {namespace}: {e}")
            return NamespaceStatus(
                name=namespace,
                status="Active",
                pods_count=0,
                pods_running=0,
                pods_failed=0,
                pods_pending=0,
                services_count=0,
                deployments_count=0,
                critical_pods=[],
                resource_usage={}
            )

    def get_pods_summary(self, namespaces: Dict[str, NamespaceStatus]) -> Dict[str, int]:
        """Obtener resumen de pods por estado"""
        summary = {
            'total': 0,
            'running': 0,
            'failed': 0,
            'pending': 0,
            'succeeded': 0,
            'unknown': 0
        }
        
        for namespace in namespaces.values():
            summary['total'] += namespace.pods_count
            summary['running'] += namespace.pods_running
            summary['failed'] += namespace.pods_failed
            summary['pending'] += namespace.pods_pending
        
        return summary
    

    
    def assess_cluster_health(self, cluster: ClusterConfig, 
                            operators: Dict[str, str], 
                            nodes: Dict[str, bool],
                            metrics: Dict[str, Dict[str, float]]) -> Tuple[str, List[str]]:
        """Evaluar salud general del cluster"""
        critical_issues = []
        
        # Verificar operadores
        for operator, status in operators.items():
            if status not in ['AsExpected', 'OK', 'RollOutDone']:
                critical_issues.append(f"Operador {operator} en estado: {status}")
        
        # Verificar nodos
        down_nodes = [node for node, is_up in nodes.items() if not is_up]
        if down_nodes:
            critical_issues.append(f"Nodos caídos: {', '.join(down_nodes)}")
        
        # Verificar métricas críticas
        memory_threshold = float(os.getenv('MEMORY_CRITICAL_THRESHOLD', 90))
        cpu_threshold = float(os.getenv('CPU_CRITICAL_THRESHOLD', 85))
        disk_threshold = float(os.getenv('DISK_CRITICAL_THRESHOLD', 85))
        
        for node_name, memory_pct in metrics.get('memory', {}).items():
            if memory_pct < (100 - memory_threshold):
                critical_issues.append(f"Nodo {node_name}: Memoria crítica ({memory_pct:.1f}% disponible)")
        
        for node_name, cpu_pct in metrics.get('cpu', {}).items():
            if cpu_pct > cpu_threshold:
                critical_issues.append(f"Nodo {node_name}: CPU crítica ({cpu_pct:.1f}% en uso)")
        
        for node_name, disk_pct in metrics.get('disk', {}).items():
            if disk_pct < (100 - disk_threshold):
                critical_issues.append(f"Nodo {node_name}: Disco crítico ({disk_pct:.1f}% disponible)")
        
        # Determinar salud general
        if critical_issues:
            health = "CRITICAL"
        else:
            health = "HEALTHY"
        
        return health, critical_issues
    
    def monitor_cluster(self, cluster: ClusterConfig) -> ClusterStatus:
        """Monitorear un cluster específico"""
        console.print(f"[blue]Monitoreando cluster: {cluster.name}[/blue]")
        
        try:
            # Probar conectividad con el cluster primero
            if not self.test_openshift_api_connection(cluster):
                raise Exception(f"No se puede conectar al cluster {cluster.name}")
            
            # Obtener estado de operadores
            operators = self.check_cluster_operators(cluster)
            
            # Obtener estado de nodos
            nodes = self.check_nodes_status(cluster)
            
            # Obtener métricas de recursos
            metrics = self.get_resource_metrics(cluster)
            
            # Obtener estado de namespaces y pods
            namespaces = self.get_namespaces_status(cluster)
            pods_summary = self.get_pods_summary(namespaces)
            
            # Evaluar salud del cluster
            health, critical_issues = self.assess_cluster_health(
                cluster, operators, nodes, metrics
            )
            
            # Agregar problemas de pods a los issues críticos
            for namespace_name, namespace_status in namespaces.items():
                if namespace_status.critical_pods:
                    for pod in namespace_status.critical_pods:
                        critical_issues.append(f"Pod {pod} en namespace {namespace_name} tiene problemas")
            
            # Crear estado del cluster
            status = ClusterStatus(
                name=cluster.name,
                timestamp=datetime.now(),
                operators_status=operators,
                nodes_status=nodes,
                resource_metrics=metrics,
                overall_health=health,
                critical_issues=critical_issues,
                namespaces_status=namespaces,
                pods_summary=pods_summary
            )
            
            return status
            
        except Exception as e:
            logger.error(f"Error monitoreando cluster {cluster.name}: {e}")
            # Retornar estado de error
            return ClusterStatus(
                name=cluster.name,
                timestamp=datetime.now(),
                operators_status={},
                nodes_status={},
                resource_metrics={},
                overall_health="ERROR",
                critical_issues=[f"Error de monitoreo: {str(e)}"],
                namespaces_status={}, # Inicializar namespaces_status
                pods_summary={} # Inicializar pods_summary
            )
    
    def detect_changes(self, cluster_name: str) -> Dict[str, List[str]]:
        """Detectar cambios significativos en el cluster de manera inteligente"""
        if cluster_name not in self.previous_statuses:
            return {
                "new_problems": ["Primera ejecución del monitoreo"],
                "resolved_problems": [],
                "status_changes": [],
                "resource_changes": []
            }
        
        previous = self.previous_statuses[cluster_name]
        current = self.cluster_statuses[cluster_name]
        
        changes = {
            "new_problems": [],
            "resolved_problems": [],
            "status_changes": [],
            "resource_changes": []
        }
        
        # Cambios en operadores
        for operator, status in current.operators_status.items():
            if operator not in previous.operators_status:
                changes["new_problems"].append(f"Nuevo operador: {operator} ({status})")
            elif previous.operators_status[operator] != status:
                if status not in ['AsExpected', 'OK', 'RollOutDone']:
                    changes["new_problems"].append(f"Operador {operator} degradado: {status}")
                else:
                    changes["resolved_problems"].append(f"Operador {operator} recuperado: {status}")
                changes["status_changes"].append(f"Operador {operator}: {previous.operators_status[operator]} → {status}")
        
        # Cambios en nodos
        for node, is_up in current.nodes_status.items():
            if node not in previous.nodes_status:
                changes["new_problems"].append(f"Nuevo nodo: {node}")
            elif previous.nodes_status[node] != is_up:
                if not is_up:
                    changes["new_problems"].append(f"Nodo {node} caído")
                else:
                    changes["resolved_problems"].append(f"Nodo {node} recuperado")
                changes["status_changes"].append(f"Nodo {node}: {'arriba' if is_up else 'abajo'}")
        
        # Cambios en salud general
        if previous.overall_health != current.overall_health:
            if current.overall_health in ['CRITICAL', 'ERROR']:
                changes["new_problems"].append(f"Salud del cluster degradada: {current.overall_health}")
            elif previous.overall_health in ['CRITICAL', 'ERROR'] and current.overall_health == 'HEALTHY':
                changes["resolved_problems"].append(f"Cluster recuperado: {current.overall_health}")
            changes["status_changes"].append(f"Salud del cluster: {previous.overall_health} → {current.overall_health}")
        
        # Cambios en pods (nuevos problemas y recuperaciones)
        if hasattr(current, 'namespaces_status') and hasattr(previous, 'namespaces_status'):
            current_critical_pods = set()
            previous_critical_pods = set()
            
            # Obtener pods críticos actuales
            for ns_name, ns_status in current.namespaces_status.items():
                for pod in ns_status.critical_pods:
                    current_critical_pods.add(f"{pod} ({ns_name})")
            
            # Obtener pods críticos anteriores
            for ns_name, ns_status in previous.namespaces_status.items():
                for pod in ns_status.critical_pods:
                    previous_critical_pods.add(f"{pod} ({ns_name})")
            
            # Nuevos pods con problemas
            new_critical_pods = current_critical_pods - previous_critical_pods
            for pod in new_critical_pods:
                changes["new_problems"].append(f"Pod con problemas: {pod}")
            
            # Pods recuperados
            resolved_critical_pods = previous_critical_pods - current_critical_pods
            for pod in resolved_critical_pods:
                changes["resolved_problems"].append(f"Pod recuperado: {pod}")
        
        # Cambios en métricas de recursos
        if hasattr(current, 'resource_metrics') and hasattr(previous, 'resource_metrics'):
            for node_name in current.resource_metrics:
                if node_name in previous.resource_metrics:
                    prev_cpu = previous.resource_metrics[node_name].get('cpu', 0)
                    curr_cpu = current.resource_metrics[node_name].get('cpu', 0)
                    prev_memory = previous.resource_metrics[node_name].get('memory', 0)
                    curr_memory = current.resource_metrics[node_name].get('memory', 0)
                    
                    # Alertas de CPU
                    if curr_cpu > 85 and prev_cpu <= 85:
                        changes["new_problems"].append(f"Nodo {node_name}: CPU crítico ({curr_cpu:.1f}%)")
                    elif curr_cpu <= 70 and prev_cpu > 70:
                        changes["resolved_problems"].append(f"Nodo {node_name}: CPU normalizado ({curr_cpu:.1f}%)")
                    
                    # Alertas de memoria
                    if curr_memory > 90 and prev_memory <= 90:
                        changes["new_problems"].append(f"Nodo {node_name}: Memoria crítica ({curr_memory:.1f}%)")
                    elif curr_memory <= 80 and prev_memory > 80:
                        changes["resolved_problems"].append(f"Nodo {node_name}: Memoria normalizada ({curr_memory:.1f}%)")
        
        return changes
    
    def generate_markdown_report(self, cluster_name: str) -> str:
        """Generar reporte en markdown para un cluster"""
        if cluster_name not in self.cluster_statuses:
            return f"# Error: No hay datos para el cluster {cluster_name}"
        
        status = self.cluster_statuses[cluster_name]
        
        # Crear reporte markdown
        report = f"""# Reporte de Estado del Cluster OpenShift

**Cluster:** {status.name}  
**Fecha:** {status.timestamp.strftime('%Y-%m-%d %H:%M:%S')}  
**Estado General:** {status.overall_health}  

## 🟢 Estado de Operadores

| Operador | Estado |
|----------|---------|
"""
        
        for operator, operator_status in status.operators_status.items():
            emoji = "✅" if operator_status in ['AsExpected', 'OK', 'RollOutDone'] else "⚠️"
            report += f"| {operator} | {emoji} {operator_status} |\n"
        
        report += f"""
## 🖥️ Estado de Nodos

| Nodo | Estado |
|------|---------|
"""
        
        for node, is_up in status.nodes_status.items():
            emoji = "✅" if is_up else "❌"
            status_text = "Operativo" if is_up else "Caído"
            report += f"| {node} | {emoji} {status_text} |\n"
        
        # Métricas de recursos
        if status.resource_metrics:
            report += f"""
## 📊 Métricas de Recursos

### Memoria Disponible por Nodo
| Nodo | Memoria Disponible |
|------|-------------------|
"""
            for node, memory_pct in status.resource_metrics.get('memory', {}).items():
                emoji = "🟢" if memory_pct > 80 else "🟡" if memory_pct > 60 else "🔴"
                report += f"| {node} | {emoji} {memory_pct:.1f}% |\n"
            
            report += f"""
### Uso de CPU por Nodo
| Nodo | Uso de CPU |
|------|-------------|
"""
            for node, cpu_pct in status.resource_metrics.get('cpu', {}).items():
                emoji = "🟢" if cpu_pct < 50 else "🟡" if cpu_pct < 80 else "🔴"
                report += f"| {node} | {emoji} {cpu_pct:.1f}% |\n"

        # Resumen de Pods
        if status.pods_summary:
            report += f"""
## 🐳 Resumen de Pods

| Estado | Cantidad |
|--------|----------|
| Total | {status.pods_summary.get('total', 0)} |
| Running | {status.pods_summary.get('running', 0)} |
| Failed | {status.pods_summary.get('failed', 0)} |
| Pending | {status.pods_summary.get('pending', 0)} |
"""

        # Estado de Namespaces
        if status.namespaces_status:
            report += f"""
## 📁 Estado de Namespaces

| Namespace | Pods | Running | Failed | Pending | Services | Deployments |
|-----------|------|---------|--------|---------|----------|-------------|
"""
            for namespace_name, namespace_status in status.namespaces_status.items():
                # Solo mostrar namespaces con pods
                if namespace_status.pods_count > 0:
                    status_emoji = "🟢" if namespace_status.pods_failed == 0 else "🟡" if namespace_status.pods_pending > 0 else "🔴"
                    report += f"| {namespace_name} | {status_emoji} {namespace_status.pods_count} | {namespace_status.pods_running} | {namespace_status.pods_failed} | {namespace_status.pods_pending} | {namespace_status.services_count} | {namespace_status.deployments_count} |\n"
            
            # Mostrar pods críticos si los hay
            critical_pods = []
            for namespace_name, namespace_status in status.namespaces_status.items():
                if namespace_status.critical_pods:
                    for pod in namespace_status.critical_pods:
                        critical_pods.append(f"{pod} ({namespace_name})")
            
            if critical_pods:
                report += f"""
### 🚨 Pods con Problemas

"""
                for pod in critical_pods:
                    report += f"- {pod}\n"
        

        
        # Problemas críticos
        if status.critical_issues:
            report += f"""
## 🚨 Problemas Críticos

"""
            for issue in status.critical_issues:
                report += f"- {issue}\n"
        else:
            report += f"""
## ✅ Estado del Sistema

No se detectaron problemas críticos.
"""
        
        # Cambios detectados
        changes = self.detect_changes(cluster_name)
        if changes:
            report += f"""
## 📈 Cambios Detectados

"""
            for change_type, change_list in changes.items():
                if change_list:
                    report += f"**{change_type.replace('_', ' ').title()}**: \n"
                    for change in change_list:
                        report += f"- {change}\n"
        
        report += f"""
---
*Reporte generado automáticamente por OpenShift Monitor*
"""
        
        return report
    
    def save_report(self, cluster_name: str, report_content: str):
        """Guardar reporte en archivo"""
        try:
            reports_dir = os.getenv('REPORTS_DIRECTORY', './reports')
            os.makedirs(reports_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{cluster_name}_{timestamp}.md"
            filepath = os.path.join(reports_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Reporte guardado: {filepath}")
            
            # Limpiar reportes antiguos si está habilitado
            if os.getenv('BACKUP_REPORTS', 'true').lower() == 'true':
                self.cleanup_old_reports(reports_dir)
                
        except Exception as e:
            logger.error(f"Error guardando reporte: {e}")
    
    def cleanup_old_reports(self, reports_dir: str):
        """Limpiar reportes antiguos"""
        try:
            max_age_days = int(os.getenv('MAX_REPORTS_AGE_DAYS', 3))
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            for filename in os.listdir(reports_dir):
                if filename.endswith('.md'):
                    filepath = os.path.join(reports_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    
                    if file_time < cutoff_date:
                        os.remove(filepath)
                        logger.info(f"Reporte antiguo eliminado: {filename}")
                        
        except Exception as e:
            logger.error(f"Error limpiando reportes antiguos: {e}")
    
    def display_status_table(self):
        """Mostrar tabla de estado de todos los clusters"""
        table = Table(title="Estado de Clusters OpenShift")
        table.add_column("Cluster", style="cyan")
        table.add_column("Estado", style="green")
        table.add_column("Operadores", style="blue")
        table.add_column("Nodos", style="yellow")

        table.add_column("Última Verificación", style="magenta")
        
        for cluster_name, status in self.cluster_statuses.items():
            # Contar operadores OK
            ok_operators = sum(1 for s in status.operators_status.values() 
                             if s in ['AsExpected', 'OK', 'RollOutDone'])
            total_operators = len(status.operators_status)
            
            # Contar nodos operativos
            ok_nodes = sum(1 for is_up in status.nodes_status.values() if is_up)
            total_nodes = len(status.nodes_status)
            

            
            # Estado con emoji
            health_emoji = {
                "HEALTHY": "🟢",
                "WARNING": "🟡", 
                "CRITICAL": "🔴",
                "ERROR": "❌"
            }
            health_display = f"{health_emoji.get(status.overall_health, '❓')} {status.overall_health}"
            
            table.add_row(
                cluster_name,
                health_display,
                f"{ok_operators}/{total_operators}",
                f"{ok_nodes}/{total_nodes}",
                status.timestamp.strftime('%H:%M:%S')
            )
        
        console.print(table)
    
    def run_monitoring_cycle(self):
        """Ejecutar ciclo completo de monitoreo"""
        console.print("\n[bold blue]🔄 Iniciando ciclo de monitoreo...[/bold blue]")
        
        for cluster in self.clusters:
            try:
                # Monitorear cluster
                status = self.monitor_cluster(cluster)
                
                # Guardar estado anterior
                if cluster.name in self.cluster_statuses:
                    self.previous_statuses[cluster.name] = self.cluster_statuses[cluster.name]
                
                # Actualizar estado actual
                self.cluster_statuses[cluster.name] = status
                
                # Generar y guardar reporte
                report_content = self.generate_markdown_report(cluster.name)
                self.save_report(cluster.name, report_content)
                
                # Detectar cambios
                changes = self.detect_changes(cluster.name)
                if changes:
                    console.print(f"[yellow]⚠️ Cambios detectados en {cluster.name}:[/yellow]")
                    for change_type, change_list in changes.items():
                        if change_list:
                            console.print(f"  - **{change_type.replace('_', ' ').title()}**:")
                            for change in change_list:
                                console.print(f"    - {change}")
                
                # Notificar si hay problemas críticos
                if status.critical_issues:
                    console.print(f"[red]🚨 Problemas críticos en {cluster.name}:[/red]")
                    for issue in status.critical_issues:
                        console.print(f"  - {issue}")
                    
                    # Enviar notificación de Telegram si está configurado
                    if self.telegram_bot:
                        try:
                            asyncio.run(self.telegram_bot.send_cluster_status_notification(cluster.name, status))
                        except Exception as e:
                            logger.error(f"Error enviando notificación de Telegram: {e}")
                
                # Enviar alertas inteligentes si están habilitadas
                if self.telegram_bot:
                    self.send_smart_alerts(cluster.name, changes)
                
            except Exception as e:
                logger.error(f"Error en ciclo de monitoreo para {cluster.name}: {e}")
                console.print(f"[red]❌ Error monitoreando {cluster.name}: {e}[/red]")
        
        # Mostrar tabla de estado
        self.display_status_table()
        console.print(f"\n[green]✅ Ciclo de monitoreo completado a las {datetime.now().strftime('%H:%M:%S')}[/green]")

    def generate_auto_summary(self) -> str:
        """Generar resumen automático del estado del cluster"""
        if not self.cluster_statuses:
            return "⚠️ No hay datos de clusters disponibles"
        
        summary = "📊 **RESUMEN AUTOMÁTICO DEL CLUSTER**\n"
        summary += f"🕐 **Hora:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        
        total_pods = 0
        total_running_pods = 0
        total_failed_pods = 0
        total_pending_pods = 0
        critical_issues_count = 0
        
        for cluster_name, status in self.cluster_statuses.items():
            summary += f"🏠 **Cluster:** {cluster_name}\n"
            summary += f"🏥 **Estado:** {self._get_health_emoji(status.overall_health)} {status.overall_health}\n"
            
            # Estado de nodos
            total_nodes = len(status.nodes_status)
            operational_nodes = sum(1 for is_up in status.nodes_status.values() if is_up)
            summary += f"🖥️ **Nodos:** {operational_nodes}/{total_nodes} ✅\n"
            
            # Estado de operadores
            total_operators = len(status.operators_status)
            ok_operators = sum(1 for s in status.operators_status.values() if s in ['AsExpected', 'OK', 'RollOutDone'])
            summary += f"⚙️ **Operadores:** {ok_operators}/{total_operators} ✅\n"
            
            # Métricas de recursos (promedio)
            if status.resource_metrics:
                cpu_values = [metrics.get('cpu', 0) for metrics in status.resource_metrics.values()]
                memory_values = [metrics.get('memory', 0) for metrics in status.resource_metrics.values()]
                
                if cpu_values:
                    avg_cpu = sum(cpu_values) / len(cpu_values)
                    cpu_emoji = "🟢" if avg_cpu < 50 else "🟡" if avg_cpu < 80 else "🔴"
                    summary += f"📈 **CPU Promedio:** {cpu_emoji} {avg_cpu:.1f}%\n"
                
                if memory_values:
                    avg_memory = sum(memory_values) / len(memory_values)
                    memory_emoji = "🟢" if avg_memory < 70 else "🟡" if avg_memory < 90 else "🔴"
                    summary += f"💾 **Memoria Promedio:** {memory_emoji} {avg_memory:.1f}%\n"
            
            # Resumen de pods
            if hasattr(status, 'pods_summary') and status.pods_summary:
                pods_summary = status.pods_summary
                total_pods += pods_summary.get('total', 0)
                total_running_pods += pods_summary.get('running', 0)
                total_failed_pods += pods_summary.get('failed', 0)
                total_pending_pods += pods_summary.get('pending', 0)
                
                summary += f"🐳 **Pods:** {pods_summary.get('total', 0)}\n"
                summary += f"  • Running: {pods_summary.get('running', 0)} ✅\n"
                summary += f"  • Failed: {pods_summary.get('failed', 0)} ❌\n"
                summary += f"  • Pending: {pods_summary.get('pending', 0)} ⏳\n"
            
            # Pods con problemas específicos
            if hasattr(status, 'namespaces_status') and status.namespaces_status:
                critical_pods = []
                for ns_name, ns_status in status.namespaces_status.items():
                    if ns_status.critical_pods:
                        critical_pods.extend([f"{pod} ({ns_name})" for pod in ns_status.critical_pods])
                
                if critical_pods:
                    summary += f"🚨 **Pods con Problemas:** {len(critical_pods)}\n"
                    for pod in critical_pods[:3]:  # Mostrar solo los primeros 3
                        summary += f"  • {pod}\n"
                    if len(critical_pods) > 3:
                        summary += f"  ... y {len(critical_pods) - 3} más\n"
                    critical_issues_count += len(critical_pods)
            
            # Problemas críticos generales
            if status.critical_issues:
                summary += f"⚠️ **Problemas Críticos:** {len(status.critical_issues)}\n"
                for issue in status.critical_issues[:2]:  # Mostrar solo los primeros 2
                    summary += f"  • {issue}\n"
                if len(status.critical_issues) > 2:
                    summary += f"  ... y {len(status.critical_issues) - 2} más\n"
                critical_issues_count += len(status.critical_issues)
            
            summary += "\n" + "─" * 40 + "\n\n"
        
        # Resumen general
        summary += f"**📊 RESUMEN GENERAL:**\n"
        summary += f"🏠 **Clusters:** {len(self.cluster_statuses)}\n"
        summary += f"🐳 **Total Pods:** {total_pods}\n"
        summary += f"✅ **Pods Running:** {total_running_pods}\n"
        summary += f"❌ **Pods Failed:** {total_failed_pods}\n"
        summary += f"⏳ **Pods Pending:** {total_pending_pods}\n"
        summary += f"🚨 **Problemas Críticos:** {critical_issues_count}\n"
        
        # Estado general del sistema
        if critical_issues_count == 0:
            summary += f"\n🎉 **Estado del Sistema:** 🟢 SALUDABLE"
        elif critical_issues_count < 5:
            summary += f"\n⚠️ **Estado del Sistema:** 🟡 ADVERTENCIA"
        else:
            summary += f"\n🚨 **Estado del Sistema:** 🔴 CRÍTICO"
        
        return summary
    
    def _get_health_emoji(self, health: str) -> str:
        """Obtener emoji para el estado de salud"""
        health_emoji = {
            "HEALTHY": "🟢",
            "WARNING": "🟡", 
            "CRITICAL": "🔴",
            "ERROR": "❌"
        }
        return health_emoji.get(health, "❓")

    def send_smart_alerts(self, cluster_name: str, changes: Dict[str, List[str]]):
        """Enviar alertas inteligentes basadas en cambios detectados"""
        if not self.telegram_bot:
            return
        
        # Solo enviar alertas si están habilitadas
        if not os.getenv('TELEGRAM_SMART_ALERTS', 'true').lower() == 'true':
            return
        
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not telegram_chat_id or telegram_chat_id == '123456789':
            return
        
        try:
            # Alertas de nuevos problemas
            if changes.get('new_problems'):
                alert_message = f"🚨 **ALERTA: Nuevos Problemas en {cluster_name}**\n\n"
                for problem in changes['new_problems']:
                    alert_message += f"• {problem}\n"
                alert_message += f"\n🕐 **Hora:** {datetime.now().strftime('%H:%M:%S')}"
                
                asyncio.run(self.telegram_bot.send_message_to_chat(telegram_chat_id, alert_message))
                logger.info(f"Alerta de nuevos problemas enviada para {cluster_name}")
            
            # Notificaciones de problemas resueltos
            if changes.get('resolved_problems') and os.getenv('TELEGRAM_RECOVERY_NOTIFICATIONS', 'true').lower() == 'true':
                recovery_message = f"🎉 **PROBLEMA RESUELTO en {cluster_name}**\n\n"
                for resolved in changes['resolved_problems']:
                    recovery_message += f"• {resolved}\n"
                recovery_message += f"\n🕐 **Hora:** {datetime.now().strftime('%H:%M:%S')}"
                
                asyncio.run(self.telegram_bot.send_message_to_chat(telegram_chat_id, recovery_message))
                logger.info(f"Notificación de recuperación enviada para {cluster_name}")
            
            # Cambios de estado importantes
            if changes.get('status_changes'):
                status_message = f"⚠️ **Cambios de Estado en {cluster_name}**\n\n"
                for change in changes['status_changes']:
                    status_message += f"• {change}\n"
                status_message += f"\n🕐 **Hora:** {datetime.now().strftime('%H:%M:%S')}"
                
                asyncio.run(self.telegram_bot.send_message_to_chat(telegram_chat_id, status_message))
                logger.info(f"Notificación de cambios de estado enviada para {cluster_name}")
                
        except Exception as e:
            logger.error(f"Error enviando alertas inteligentes para {cluster_name}: {e}")

def main():
    """Función principal"""
    try:
        console.print("[bold blue]🚀 Iniciando OpenShift Monitor...[/bold blue]")
        
        # Crear monitor
        monitor = OpenShiftMonitor()
        
        # Mostrar configuración
        console.print(f"[green]✅ Configurados {len(monitor.clusters)} clusters[/green]")
        for cluster in monitor.clusters:
            console.print(f"  - {cluster.name}: {cluster.api_url}")
        
        # Configurar programación
        monitoring_interval = int(os.getenv('MONITORING_INTERVAL', 300))  # 5 minutos por defecto
        report_interval = int(os.getenv('REPORT_INTERVAL', 3600))  # 1 hora por defecto
        
        console.print(f"[blue]⏰ Intervalo de monitoreo: {monitoring_interval} segundos[/blue]")
        console.print(f"[blue]📊 Intervalo de reportes: {report_interval} segundos[/blue]")
        console.print(f"[blue]🚨 Alertas inteligentes: Habilitadas[/blue]")
        console.print(f"[blue]🎉 Notificaciones de recuperación: Habilitadas[/blue]")
        
        # Programar tareas
        schedule.every(monitoring_interval).seconds.do(monitor.run_monitoring_cycle)
        
        # Ejecutar monitoreo inicial
        monitor.run_monitoring_cycle()
        
        # Bucle principal
        console.print("[green]🔄 Monitor ejecutándose. Presiona Ctrl+C para detener...[/green]")
        console.print("[yellow]💡 El monitor enviará alertas automáticamente cuando detecte problemas nuevos[/yellow]")
        
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Deteniendo monitor...[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Error fatal: {e}[/red]")
        logger.error(f"Error fatal: {e}")
        raise

if __name__ == "__main__":
    main() 