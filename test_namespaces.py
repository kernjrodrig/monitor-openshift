#!/usr/bin/env python3
"""
Script de prueba para verificar el monitoreo de namespaces y pods
"""

import os
import sys
import subprocess
from datetime import datetime

def test_oc_connection():
    """Probar conexión con OpenShift"""
    print("🔍 Probando conexión con OpenShift...")
    
    try:
        # Verificar si oc está disponible
        result = subprocess.run(['oc', 'whoami'], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✅ Conectado como: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Error de conexión: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ Cliente 'oc' no encontrado. Instala OpenShift CLI")
        return False
    except subprocess.TimeoutExpired:
        print("❌ Timeout en la conexión")
        return False

def test_namespaces():
    """Probar obtención de namespaces"""
    print("\n📁 Probando obtención de namespaces...")
    
    try:
        # Obtener namespaces
        result = subprocess.run([
            'oc', 'get', 'namespaces', 
            '--no-headers', 
            '--output=custom-columns=NAME:.metadata.name,STATUS:.status.phase'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            namespaces = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        namespaces.append((parts[0], parts[1]))
            
            print(f"✅ Encontrados {len(namespaces)} namespaces:")
            for name, status in namespaces[:10]:  # Mostrar solo los primeros 10
                print(f"  • {name}: {status}")
            
            if len(namespaces) > 10:
                print(f"  ... y {len(namespaces) - 10} más")
            
            return namespaces
        else:
            print(f"❌ Error obteniendo namespaces: {result.stderr}")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def test_pods_in_namespace(namespace):
    """Probar obtención de pods en un namespace específico"""
    print(f"\n🐳 Probando obtención de pods en namespace '{namespace}'...")
    
    try:
        # Obtener pods
        result = subprocess.run([
            'oc', 'get', 'pods', '-n', namespace,
            '--no-headers',
            '--output=custom-columns=NAME:.metadata.name,STATUS:.status.phase,READY:.status.containerStatuses[*].ready'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            pods = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        pods.append((parts[0], parts[1]))
            
            print(f"✅ Encontrados {len(pods)} pods:")
            for name, status in pods[:5]:  # Mostrar solo los primeros 5
                print(f"  • {name}: {status}")
            
            if len(pods) > 5:
                print(f"  ... y {len(pods) - 5} más")
            
            return pods
        else:
            print(f"❌ Error obteniendo pods: {result.stderr}")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def test_services_in_namespace(namespace):
    """Probar obtención de servicios en un namespace específico"""
    print(f"\n🔧 Probando obtención de servicios en namespace '{namespace}'...")
    
    try:
        # Obtener servicios
        result = subprocess.run([
            'oc', 'get', 'services', '-n', namespace,
            '--no-headers',
            '--output=custom-columns=NAME:.metadata.name'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            services = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            print(f"✅ Encontrados {len(services)} servicios:")
            for service in services[:5]:
                print(f"  • {service}")
            
            if len(services) > 5:
                print(f"  ... y {len(services) - 5} más")
            
            return services
        else:
            print(f"❌ Error obteniendo servicios: {result.stderr}")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def test_deployments_in_namespace(namespace):
    """Probar obtención de deployments en un namespace específico"""
    print(f"\n🚀 Probando obtención de deployments en namespace '{namespace}'...")
    
    try:
        # Obtener deployments
        result = subprocess.run([
            'oc', 'get', 'deployments', '-n', namespace,
            '--no-headers',
            '--output=custom-columns=NAME:.metadata.name'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            deployments = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            print(f"✅ Encontrados {len(deployments)} deployments:")
            for deployment in deployments[:5]:
                print(f"  • {deployment}")
            
            if len(deployments) > 5:
                print(f"  ... y {len(deployments) - 5} más")
            
            return deployments
        else:
            print(f"❌ Error obteniendo deployments: {result.stderr}")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def main():
    """Función principal"""
    print("🚀 Script de Prueba - Monitoreo de Namespaces y Pods")
    print("=" * 60)
    
    # Probar conexión
    if not test_oc_connection():
        print("\n❌ No se puede continuar sin conexión a OpenShift")
        sys.exit(1)
    
    # Probar namespaces
    namespaces = test_namespaces()
    if not namespaces:
        print("\n❌ No se pudieron obtener namespaces")
        sys.exit(1)
    
    # Probar con el primer namespace que tenga pods
    test_namespace = None
    for name, status in namespaces:
        if status == 'Active':
            test_namespace = name
            break
    
    if test_namespace:
        print(f"\n🎯 Probando con namespace: {test_namespace}")
        
        # Probar pods
        test_pods_in_namespace(test_namespace)
        
        # Probar servicios
        test_services_in_namespace(test_namespace)
        
        # Probar deployments
        test_deployments_in_namespace(test_namespace)
    else:
        print("\n⚠️ No se encontró un namespace activo para probar")
    
    print("\n✅ Pruebas completadas")
    print("\n💡 Si todo funcionó correctamente, el monitor debería poder obtener")
    print("   información de namespaces y pods automáticamente.")

if __name__ == "__main__":
    main() 