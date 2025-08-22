#!/bin/bash

# Script simple para levantar OpenShift Monitor
# Autor: Asistente IA

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== OPENSHIFT MONITOR - INICIADOR SIMPLE ===${NC}"
echo ""

# Función para mostrar ayuda
show_help() {
    echo -e "${BLUE}Uso: $0 [OPCIÓN]${NC}"
    echo ""
    echo "Opciones:"
    echo "  start     Iniciar el monitor (por defecto)"
    echo "  stop      Detener el monitor"
    echo "  restart   Reiniciar el monitor"
    echo "  status    Ver estado del monitor"
    echo "  logs      Ver logs del monitor"
    echo "  config    Ver configuración actual"
    echo "  help      Mostrar esta ayuda"
    echo ""
    echo "Ejemplos:"
    echo "  $0 start      # Iniciar monitor"
    echo "  $0 stop       # Detener monitor"
    echo "  $0 logs       # Ver logs"
}

# Función para verificar dependencias
check_dependencies() {
    echo -e "${YELLOW}Verificando dependencias...${NC}"
    
    # Detectar si usar Docker o Podman
    if command -v podman &> /dev/null; then
        CONTAINER_ENGINE="podman"
        COMPOSE_CMD="podman-compose"
        echo -e "${BLUE}🐳 Usando Podman${NC}"
    elif command -v docker &> /dev/null; then
        CONTAINER_ENGINE="docker"
        COMPOSE_CMD="docker-compose"
        echo -e "${BLUE}🐳 Usando Docker${NC}"
    else
        echo -e "${RED}❌ No se encontró Docker ni Podman${NC}"
        echo -e "${YELLOW}💡 Instala Docker o Podman para continuar${NC}"
        exit 1
    fi
    
    # Verificar compose
    if ! command -v $COMPOSE_CMD &> /dev/null; then
        echo -e "${RED}❌ $COMPOSE_CMD no está instalado${NC}"
        if [ "$CONTAINER_ENGINE" = "podman" ]; then
            echo -e "${YELLOW}💡 Instala: pip install podman-compose${NC}"
        else
            echo -e "${YELLOW}💡 Instala: pip install docker-compose${NC}"
        fi
        exit 1
    fi
    
    echo -e "${GREEN}✅ Dependencias verificadas${NC}"
    echo ""
}

# Función para verificar configuración
check_config() {
    echo -e "${YELLOW}Verificando configuración...${NC}"
    
    if [ ! -f config.env ]; then
        echo -e "${RED}❌ Archivo config.env no encontrado${NC}"
        echo -e "${YELLOW}💡 Copia config.env.example a config.env y configúralo${NC}"
        exit 1
    fi
    
    # Verificar variables críticas
    source config.env
    
    if [[ -z "$OPENSHIFT_TOKENS" || "$OPENSHIFT_TOKENS" == "sha256~TU_TOKEN_AQUI" ]]; then
        echo -e "${RED}❌ OPENSHIFT_TOKENS no configurado correctamente${NC}"
        echo -e "${YELLOW}💡 Actualiza config.env con tu token real${NC}"
        exit 1
    fi
    
    if [[ -z "$PROMETHEUS_URLS" || "$PROMETHEUS_URLS" == "https://prometheus-k8s-openshift-monitoring.apps.tu-cluster.com" ]]; then
        echo -e "${RED}❌ PROMETHEUS_URLS no configurado correctamente${NC}"
        echo -e "${YELLOW}💡 Actualiza config.env con tu URL real${NC}"
        exit 1
    fi
    
    if [[ -z "$ALERTMANAGER_URLS" || "$ALERTMANAGER_URLS" == "https://alertmanager-main-openshift-monitoring.apps.tu-cluster.com" ]]; then
        echo -e "${RED}❌ ALERTMANAGER_URLS no configurado correctamente${NC}"
        echo -e "${YELLOW}💡 Actualiza config.env con tu URL real${NC}"
        exit 1
    fi
    
    if [[ -z "$CLUSTER_NAMES" || "$CLUSTER_NAMES" == "prd-ocp.guzdan.com" ]]; then
        echo -e "${RED}❌ CLUSTER_NAMES no configurado correctamente${NC}"
        echo -e "${YELLOW}💡 Actualiza config.env con tu nombre de cluster real${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Configuración verificada${NC}"
    echo -e "${BLUE}📋 Clusters: $CLUSTER_NAMES${NC}"
    echo -e "${BLUE}📊 Prometheus: $PROMETHEUS_URLS${NC}"
    echo -e "${BLUE}🚨 Alertmanager: $ALERTMANAGER_URLS${NC}"
    echo ""
}

# Función para iniciar monitor
start_monitor() {
    echo -e "${YELLOW}Iniciando OpenShift Monitor...${NC}"
    
    # Crear directorios si no existen
    mkdir -p reports logs config
    
    # Verificar que config.env existe
    if [ ! -f config.env ]; then
        echo -e "${RED}❌ Archivo config.env no encontrado${NC}"
        echo -e "${YELLOW}💡 Ejecuta: ./install.sh para configurar primero${NC}"
        exit 1
    fi
    
    # Construir y ejecutar
    echo -e "${BLUE}🔨 Construyendo imagen...${NC}"
    $COMPOSE_CMD build
    
    echo -e "${BLUE}🚀 Iniciando servicios...${NC}"
    $COMPOSE_CMD up -d
    
    echo -e "${GREEN}✅ Monitor iniciado exitosamente${NC}"
    echo ""
    show_status
}

# Función para detener monitor
stop_monitor() {
    echo -e "${YELLOW}Deteniendo OpenShift Monitor...${NC}"
    
    $COMPOSE_CMD down
    
    echo -e "${GREEN}✅ Monitor detenido${NC}"
}

# Función para reiniciar monitor
restart_monitor() {
    echo -e "${YELLOW}Reiniciando OpenShift Monitor...${NC}"
    
    $COMPOSE_CMD restart
    
    echo -e "${GREEN}✅ Monitor reiniciado${NC}"
}

# Función para mostrar estado
show_status() {
    echo -e "${BLUE}📊 Estado del monitor:${NC}"
    $COMPOSE_CMD ps
    
    echo ""
    echo -e "${BLUE}📋 Información útil:${NC}"
    echo -e "  • Monitor: http://localhost:8080"
    echo -e "  • Reportes: http://localhost:8081"
    echo -e "  • Logs: $0 logs"
    echo -e "  • Detener: $0 stop"
    echo -e "  • Reiniciar: $0 restart"
}

# Función para mostrar logs
show_logs() {
    echo -e "${YELLOW}Mostrando logs del monitor...${NC}"
    echo -e "${BLUE}💡 Presiona Ctrl+C para salir${NC}"
    echo ""
    
    $COMPOSE_CMD logs -f openshift-monitor
}

# Función para mostrar configuración
show_config() {
    echo -e "${BLUE}=== CONFIGURACIÓN ACTUAL ===${NC}"
    echo ""
    
    if [ -f config.env ]; then
        cat config.env
    else
        echo -e "${RED}❌ Archivo config.env no encontrado${NC}"
    fi
}

# Función principal
main() {
    case "${1:-start}" in
        start)
            check_dependencies
            check_config
            start_monitor
            ;;
        stop)
            check_dependencies
            stop_monitor
            ;;
        restart)
            check_dependencies
            restart_monitor
            ;;
        status)
            check_dependencies
            show_status
            ;;
        logs)
            check_dependencies
            show_logs
            ;;
        config)
            show_config
            ;;
        help|-h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}❌ Opción desconocida: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

# Ejecutar función principal
main "$@" 